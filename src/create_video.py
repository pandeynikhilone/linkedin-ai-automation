import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
OUTPUT_FILE = ROOT / "linkedin_video.mp4"
WIDTH = 1080
HEIGHT = 1350
FPS = 24
SLIDE_SECONDS = 3.4
TRANSITION_SECONDS = 0.28
# LinkedIn's published member video guidance lists 30 Mbps as the upper
# bitrate. For this ~15.9 s clip, CBR at 30 Mbps produces about 60 MB.
TARGET_BITRATE = "30M"
TARGET_MIN_BYTES = 50_000_000
TARGET_MAX_BYTES = 70_000_000

PAPER = (248, 247, 239)
PAPER_DARK = (239, 240, 228)
WHITE = (255, 254, 250)
INK = (26, 39, 31)
GREEN = (40, 91, 67)
GREEN_DARK = (21, 58, 42)
LIME = (211, 239, 124)
MUTED = (88, 104, 92)
LINE = (215, 221, 211)
TEAL = (111, 166, 151)
CLAY = (199, 119, 91)
OCHRE = (220, 177, 92)
LAVENDER = (231, 227, 247)
PALE_BLUE = (221, 232, 241)

FONT_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]
FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]


def load_font(size, bold=False):
    paths = FONT_BOLD_PATHS if bold else FONT_REGULAR_PATHS
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def draw_wrapped(draw, text, xy, font, fill, max_width, line_gap=12, max_lines=5):
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,:;") + "..."
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += max(1, bbox[3] - bbox[1]) + line_gap
    return y


def draw_arrow(draw, start, end, fill, width=5):
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 18
    left = (end[0] - size * math.cos(angle - 0.55), end[1] - size * math.sin(angle - 0.55))
    right = (end[0] - size * math.cos(angle + 0.55), end[1] - size * math.sin(angle + 0.55))
    draw.polygon([end, left, right], fill=fill)


def draw_database(draw, box):
    x1, y1, x2, y2 = box
    layer_h = max(36, (y2 - y1) // 4)
    for index, color in enumerate([GREEN, TEAL, OCHRE]):
        top = y1 + index * layer_h
        draw.ellipse((x1, top, x2, top + 48), fill=color, outline=INK, width=3)
        draw.rectangle((x1, top + 22, x2, top + layer_h), fill=color)
        draw.arc((x1, top + layer_h - 48, x2, top + layer_h + 12), 0, 180, fill=INK, width=3)
        draw.arc((x1, top, x2, top + 48), 180, 360, fill=INK, width=3)


def draw_visual(draw, kind, box, slide_index):
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    card_colors = [WHITE, (236, 242, 229), PALE_BLUE, (248, 235, 224), LAVENDER]
    fill = card_colors[slide_index % len(card_colors)]
    draw.rounded_rectangle(box, radius=30, fill=fill, outline=LINE, width=2)

    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    left = x1 + 80
    right = x2 - 80
    top = y1 + 52
    bottom = y2 - 52

    if kind == "chart":
        base_y = bottom - 8
        draw.line((left, top + 20, left, base_y), fill=INK, width=5)
        draw.line((left, base_y, right, base_y), fill=INK, width=5)
        bars = [0.36, 0.62, 0.48, 0.82, 0.69]
        bar_w = max(44, width // 15)
        gap = (right - left - len(bars) * bar_w) // (len(bars) + 1)
        for i, value in enumerate(bars):
            bx = left + gap + i * (bar_w + gap)
            by = base_y - int((base_y - top) * value)
            color = [TEAL, GREEN, OCHRE, CLAY, GREEN][i]
            draw.rounded_rectangle((bx, by, bx + bar_w, base_y), radius=10, fill=color)
        points = [(left + gap, base_y - int((base_y-top)*0.3)),
                  (left + gap*2 + bar_w, base_y - int((base_y-top)*0.72)),
                  (left + gap*3 + bar_w*2, base_y - int((base_y-top)*0.53)),
                  (left + gap*4 + bar_w*3, base_y - int((base_y-top)*0.88))]
        draw.line(points, fill=GREEN_DARK, width=5)
        for point in points:
            px, py = point
            draw.ellipse((px-8, py-8, px+8, py+8), fill=LIME, outline=GREEN_DARK, width=3)

    elif kind == "flow":
        node_w = (right - left - 48) // 3
        node_y = cy - 46
        colors = [LAVENDER, (215, 239, 191), PALE_BLUE]
        for i, label_color in enumerate(colors):
            x = left + i * (node_w + 24)
            draw.rounded_rectangle((x, node_y, x + node_w, node_y + 92), radius=20, fill=label_color, outline=GREEN, width=3)
            draw.ellipse((x + 18, node_y + 20, x + 42, node_y + 44), fill=GREEN if i != 1 else CLAY)
            draw.line((x + 20, node_y + 62, x + node_w - 18, node_y + 62), fill=MUTED, width=4)
            if i < 2:
                draw_arrow(draw, (x + node_w + 4, cy), (x + node_w + 20, cy), GREEN, width=4)

    elif kind == "code":
        editor = (left, top, right, bottom)
        draw.rounded_rectangle(editor, radius=18, fill=GREEN_DARK)
        for i, color in enumerate([CLAY, OCHRE, TEAL]):
            draw.ellipse((left + 22 + i * 28, top + 20, left + 36 + i * 28, top + 34), fill=color)
        line_y = top + 70
        line_colors = [LIME, (224, 231, 218), TEAL, (224, 231, 218), OCHRE, (224, 231, 218)]
        widths = [int(width*0.48), int(width*0.68), int(width*0.36), int(width*0.77), int(width*0.55), int(width*0.42)]
        for i, line_width in enumerate(widths):
            draw.rounded_rectangle((left + 28, line_y + i * 27, left + 28 + line_width, line_y + i * 27 + 9), radius=4, fill=line_colors[i])

    elif kind == "product":
        card_w = 330
        px = cx - card_w // 2
        py = cy - 120
        draw.rounded_rectangle((px, py, px + card_w, py + 230), radius=24, fill=WHITE, outline=GREEN, width=3)
        draw.rounded_rectangle((px + 32, py + 24, px + 122, py + 106), radius=18, fill=PALE_BLUE)
        draw.ellipse((px + 62, py + 44, px + 94, py + 76), fill=TEAL)
        for i in range(5):
            sx = px + 34 + i * 45
            draw.polygon([(sx, py+138),(sx+10,py+158),(sx+32,py+160),(sx+16,py+173),(sx+20,py+195),(sx,py+183),(sx-20,py+195),(sx-16,py+173),(sx-32,py+160),(sx-10,py+158)], fill=OCHRE)

    elif kind == "database":
        draw_database(draw, (cx - 130, cy - 120, cx + 130, cy + 130))
        for y in [cy - 55, cy + 20]:
            draw.line((cx + 170, y, cx + 260, y), fill=TEAL, width=6)
            draw.ellipse((cx + 252, y - 10, cx + 272, y + 10), fill=CLAY)

    elif kind == "form" or kind == "checklist":
        sheet = (cx - 235, cy - 145, cx + 235, cy + 145)
        draw.rounded_rectangle(sheet, radius=22, fill=WHITE, outline=GREEN, width=3)
        for i in range(4):
            yy = cy - 93 + i * 58
            if kind == "checklist":
                draw.rounded_rectangle((cx - 184, yy - 8, cx - 146, yy + 30), radius=8, fill=LIME, outline=GREEN, width=2)
                draw.line((cx - 174, yy + 10, cx - 162, yy + 20), fill=GREEN, width=4)
                draw.line((cx - 162, yy + 20, cx - 148, yy + 1), fill=GREEN, width=4)
                line_left = cx - 120
            else:
                draw.rounded_rectangle((cx - 184, yy - 8, cx - 132, yy + 26), radius=8, fill=PALE_BLUE, outline=TEAL, width=2)
                line_left = cx - 105
            draw.rounded_rectangle((line_left, yy + 2, cx + 176, yy + 13), radius=5, fill=LINE)

    elif kind == "git":
        p1 = (cx - 180, cy - 45)
        p2 = (cx, cy + 68)
        p3 = (cx + 180, cy - 50)
        draw.line([p1, p2, p3], fill=GREEN, width=7)
        draw.line((p1[0], p1[1], p1[0], p1[1]-72), fill=TEAL, width=6)
        draw.line((p3[0], p3[1], p3[0], p3[1]-72), fill=CLAY, width=6)
        for point, color in [(p1, TEAL), (p2, GREEN), (p3, CLAY), ((p1[0],p1[1]-72),LIME),((p3[0],p3[1]-72),OCHRE)]:
            px, py = point
            draw.ellipse((px-19,py-19,px+19,py+19), fill=color, outline=INK, width=3)

    elif kind == "stack":
        layer_w = 410
        layer_h = 48
        x = cx - layer_w // 2
        for i, color in enumerate([LAVENDER, (215,239,191), PALE_BLUE, (248,235,224)]):
            yy = cy - 118 + i * 57
            draw.rounded_rectangle((x + i * 8, yy, x + layer_w - i * 8, yy + layer_h), radius=14, fill=color, outline=GREEN, width=2)

    elif kind == "learning":
        draw.ellipse((cx - 112, cy - 112, cx + 112, cy + 112), fill=(255, 243, 193), outline=OCHRE, width=4)
        draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=LIME, outline=GREEN, width=4)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start = (cx + int(math.cos(rad) * 145), cy + int(math.sin(rad) * 145))
            end = (cx + int(math.cos(rad) * 200), cy + int(math.sin(rad) * 200))
            draw.line((start, end), fill=CLAY if angle % 90 == 0 else GREEN, width=5)

    else:
        # Generic connected-node drawing for topics that do not need a specialized motif.
        points = [
            (cx - 205, cy + 35), (cx - 92, cy - 85), (cx + 46, cy + 55),
            (cx + 205, cy - 72), (cx + 240, cy + 100)
        ]
        for a, b in zip(points, points[1:]):
            draw.line([a, b], fill=TEAL, width=5)
        for index, (px, py) in enumerate(points):
            radius = 29 if index == 2 else 23
            draw.ellipse((px-radius, py-radius, px+radius, py+radius),
                         fill=[LIME, LAVENDER, CLAY, PALE_BLUE, OCHRE][index],
                         outline=GREEN, width=3)


def render_slide(slide, index, total, topic, output_path):
    palette = [PAPER, (246, 246, 237), (241, 245, 236), (247, 241, 231), (242, 244, 237)]
    background = palette[index % len(palette)]
    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw = ImageDraw.Draw(image)

    # Subtle paper grain built from deterministic dots, not a photo or external image.
    seed = sum(ord(char) for char in topic) + index * 97
    for dot_index in range(300):
        x = (seed * 17 + dot_index * 193) % WIDTH
        y = (seed * 31 + dot_index * 139) % HEIGHT
        tone = (239, 239, 226) if dot_index % 2 else (252, 251, 244)
        draw.point((x, y), fill=tone)

    draw.rounded_rectangle((58, 54, WIDTH - 58, 120), radius=28, fill=GREEN_DARK)
    draw.ellipse((83, 72, 111, 100), fill=LIME)
    draw.text((130, 70), "NIKHIL PANDEY  /  BUILD NOTES", font=load_font(22, True), fill=WHITE)
    draw.text((WIDTH - 154, 75), f"{index + 1:02d} / {total:02d}", font=load_font(19, True), fill=LIME)

    draw.text((78, 164), "CAREER NOTES  •  PROJECT WORK", font=load_font(18, True), fill=GREEN)
    draw.rounded_rectangle((78, 203, 170, 212), radius=4, fill=LIME)

    title = clean_title(slide.get("title", ""))
    title_font = load_font(58, True)
    title_bottom = draw_wrapped(
        draw, title, (78, 244), title_font, INK, WIDTH - 156, line_gap=10, max_lines=3
    )

    body_font = load_font(31)
    body_top = max(title_bottom + 22, 430)
    body_bottom = draw_wrapped(
        draw, slide.get("body", ""), (80, body_top), body_font, MUTED,
        WIDTH - 160, line_gap=12, max_lines=3
    )

    # Keep copy inside the main slide content, not in a separate text footer.
    # Expand the illustration into the reclaimed space and leave only a visual progress bar.
    visual_top = max(body_bottom + 28, 650)
    visual_bottom = min(visual_top + 470, 1220)
    draw_visual(
        draw,
        slide.get("visual_type", "learning"),
        (68, visual_top, WIDTH - 68, visual_bottom),
        index,
    )

    progress_x1 = 78
    progress_x2 = WIDTH - 78
    progress_y = HEIGHT - 48
    draw.rounded_rectangle((progress_x1, progress_y, progress_x2, progress_y + 7),
                           radius=4, fill=LINE)
    fill_end = progress_x1 + int((progress_x2 - progress_x1) * ((index + 1) / total))
    draw.rounded_rectangle((progress_x1, progress_y, fill_end, progress_y + 7),
                           radius=4, fill=GREEN)
    image.save(output_path, format="PNG", optimize=True)


def clean_title(text):
    return str(text).replace("\u2014", ",").replace("\u2013", "-").strip()


def short_topic(text, max_chars=66):
    text = clean_title(text)
    return text if len(text) <= max_chars else text[:max_chars - 3].rstrip() + "..."


def validate_content(data):
    if not isinstance(data, dict):
        raise RuntimeError("content.json must contain an object.")
    if not data.get("topic") or not data.get("post") or not data.get("video_title"):
        raise RuntimeError("content.json is missing topic, post, or video title.")
    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise RuntimeError("Exactly five slides are required.")
    if len(str(data["post"]).split()) > 110:
        raise RuntimeError("LinkedIn post exceeds 110 words.")
    for index, slide in enumerate(slides, start=1):
        if not slide.get("title") or not slide.get("body"):
            raise RuntimeError(f"Slide {index} is missing a title or body.")


def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is required. Install it before rendering the MP4.")
    if not CONTENT_FILE.is_file():
        raise FileNotFoundError("content.json is missing. Run src/generate_content.py first.")

    data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    validate_content(data)

    with tempfile.TemporaryDirectory(prefix="linkedin-slides-") as temp_dir:
        temp = Path(temp_dir)
        slide_paths = []
        for index, slide in enumerate(data["slides"]):
            slide_path = temp / f"slide_{index + 1:02d}.png"
            render_slide(slide, index, len(data["slides"]), data["topic"], slide_path)
            slide_paths.append(slide_path)

        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path in slide_paths:
            args.extend(["-loop", "1", "-framerate", str(FPS), "-t", str(SLIDE_SECONDS), "-i", str(path)])

        filter_parts = []
        labels = []
        for index in range(len(slide_paths)):
            label = f"v{index}"
            filter_parts.append(
                f"[{index}:v]zoompan=z='min(zoom+0.00025,1.025)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
                f"trim=duration={SLIDE_SECONDS},setpts=PTS-STARTPTS,"
                f"settb=AVTB,format=yuv420p[{label}]"
            )
            labels.append(f"[{label}]")

        fade = TRANSITION_SECONDS
        slide_out = SLIDE_SECONDS - fade
        filter_parts.append(
            f"{labels[0]}{labels[1]}xfade=transition=fade:duration={fade}:offset={slide_out}[x1]"
        )
        previous_label = "x1"
        cumulative_duration = SLIDE_SECONDS * 2 - fade
        for slide_index in range(2, len(slide_paths)):
            next_label = f"x{slide_index}"
            offset = cumulative_duration - fade
            filter_parts.append(
                f"[{previous_label}][v{slide_index}]"
                f"xfade=transition=fade:duration={fade}:offset={offset}[{next_label}]"
            )
            previous_label = next_label
            cumulative_duration += SLIDE_SECONDS - fade

        args.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{previous_label}]",
            "-an",
            "-c:v", "libx264",
            "-preset", "medium",
            "-b:v", TARGET_BITRATE,
            "-minrate", TARGET_BITRATE,
            "-maxrate", TARGET_BITRATE,
            "-bufsize", "30M",
            "-profile:v", "high",
            "-level:v", "4.2",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            "-t", str(cumulative_duration),
            str(OUTPUT_FILE),
        ])
        print("Rendering five animated slides with slow camera movement and crossfades...")
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError("FFmpeg render failed: " + (result.stderr[-1800:] or "unknown error"))

    size_bytes = OUTPUT_FILE.stat().st_size
    if not TARGET_MIN_BYTES <= size_bytes <= TARGET_MAX_BYTES:
        raise RuntimeError(
            f"Rendered video is {size_bytes:,} bytes; the high-bitrate target is "
            f"{TARGET_MIN_BYTES:,}-{TARGET_MAX_BYTES:,} bytes. Refusing to continue."
        )
    print(
        f"Rendered {OUTPUT_FILE.name}: {size_bytes:,} bytes "
        f"({size_bytes / 1_000_000:.1f} MB), H.264 at an approximately 30 Mbit/s target."
    )

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,codec_type,width,height",
            "-show_entries", "format=format_name,duration",
            "-of", "json", str(OUTPUT_FILE),
        ],
        capture_output=True, text=True, check=False
    )
    if probe.returncode != 0:
        raise RuntimeError("FFprobe could not inspect the rendered MP4.")
    metadata = json.loads(probe.stdout)
    video_stream = next((s for s in metadata.get("streams", []) if s.get("codec_type") == "video"), None)
    duration = float(metadata.get("format", {}).get("duration", 0))
    if not video_stream or video_stream.get("codec_name") != "h264":
        raise RuntimeError("Rendered video does not contain an H.264 video stream.")
    if video_stream.get("width") != WIDTH or video_stream.get("height") != HEIGHT:
        raise RuntimeError("Rendered video dimensions differ from the 1080 x 1350 template.")
    if not 12 <= duration <= 20:
        raise RuntimeError(f"Rendered video duration is outside the expected range: {duration:.2f}s.")

    print(f"SUCCESS: created {OUTPUT_FILE.name}")
    print(f"Resolution: {WIDTH} x {HEIGHT} (4:5 portrait), {FPS} fps")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Size: {size_bytes:,} bytes")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
