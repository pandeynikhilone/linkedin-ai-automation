
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
OUTPUT_FILE = ROOT / "linkedin_video.mp4"

WIDTH = 720
HEIGHT = 900
FPS = 12
SECONDS_PER_SLIDE = 3
FRAMES_PER_SLIDE = FPS * SECONDS_PER_SLIDE

BACKGROUND = (14, 23, 42)
CARD = (25, 38, 62)
WHITE = (245, 248, 255)
MUTED = (172, 187, 208)
ACCENT = (111, 230, 191)
BLUE = (111, 164, 255)


def load_font(size, bold=False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )

    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)

    return ImageFont.load_default()


FONT_SMALL = load_font(18)
FONT_BODY = load_font(27)
FONT_TITLE = load_font(43, bold=True)
FONT_BRAND = load_font(20, bold=True)


def wrap_text(draw, text, font, max_width):
    """Wrap text to fit inside a slide."""
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [""]


def draw_lines(draw, lines, x, y, font, fill, spacing=13):
    """Draw wrapped text and return the final vertical position."""
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + spacing

    return y


def render_frame(data, slide, index, frame_index):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Decorative shapes and fixed layout.
    draw.ellipse((555, -120, 830, 155), fill=(30, 52, 78))
    draw.ellipse((-100, 720, 130, 950), fill=(26, 45, 70))

    draw.text(
        (48, 40),
        "LEARNING IN PUBLIC",
        font=FONT_BRAND,
        fill=ACCENT,
    )

    draw.text(
        (48, 81),
        str(data.get("video_title", "Career Growth")),
        font=FONT_SMALL,
        fill=MUTED,
    )

    # Slide counter.
    counter = f"{index + 1:02d} / {len(data['slides']):02d}"
    draw.text(
        (WIDTH - 48, 40),
        counter,
        font=FONT_SMALL,
        fill=WHITE,
        anchor="ra",
    )

    # Main content card.
    draw.rounded_rectangle(
        (34, 160, WIDTH - 34, HEIGHT - 130),
        radius=26,
        fill=CARD,
    )

    # Animate the title by moving it upward into position.
    progress = min(1.0, (frame_index + 1) / 10)
    vertical_offset = int((1 - progress) * 24)

    title = str(slide["title"])
    body = str(slide["body"])

    title_lines = wrap_text(draw, title, FONT_TITLE, WIDTH - 120)
    title_end = draw_lines(
        draw,
        title_lines,
        60,
        215 + vertical_offset,
        FONT_TITLE,
        WHITE,
        spacing=12,
    )

    # Accent divider.
    divider_y = title_end + 19
    draw.rounded_rectangle(
        (60, divider_y, 155, divider_y + 6),
        radius=3,
        fill=ACCENT,
    )

    body_lines = wrap_text(draw, body, FONT_BODY, WIDTH - 120)

    # Reserve room for the footer and show a concise slide.
    max_body_lines = 7
    if len(body_lines) > max_body_lines:
        body_lines = body_lines[:max_body_lines]
        while body_lines and draw.textlength(
            body_lines[-1] + "...", font=FONT_BODY
        ) > WIDTH - 120:
            body_lines[-1] = body_lines[-1][:-1]
        if body_lines:
            body_lines[-1] += "..."

    body_start = divider_y + 38

    for line_number, line in enumerate(body_lines):
        draw.text(
            (60, body_start + line_number * 48),
            line,
            font=FONT_BODY,
            fill=MUTED if progress < 1 else WHITE,
        )

    # Animated progress bar across the bottom.
    bar_left = 48
    bar_top = HEIGHT - 75
    bar_width = WIDTH - 96

    draw.rounded_rectangle(
        (bar_left, bar_top, bar_left + bar_width, bar_top + 7),
        radius=4,
        fill=(53, 68, 91),
    )

    total_progress = (
        index + min(1.0, (frame_index + 1) / FRAMES_PER_SLIDE)
    ) / len(data["slides"])

    draw.rounded_rectangle(
        (
            bar_left,
            bar_top,
            bar_left + max(1, int(bar_width * total_progress)),
            bar_top + 7,
        ),
        radius=4,
        fill=ACCENT if index == len(data["slides"]) - 1 else BLUE,
    )

    draw.text(
        (48, HEIGHT - 55),
        "CAREER • SKILLS • CONSISTENCY",
        font=FONT_SMALL,
        fill=MUTED,
    )

    return image


def main():
    if not CONTENT_FILE.exists():
        raise FileNotFoundError(
            "content.json is missing. Run generate_content.py first."
        )

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg is not installed. Install it in the GitHub Actions job."
        )

    data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))

    slides = data.get("slides")
    if not isinstance(slides, list) or len(slides) != 5:
        raise ValueError("content.json must contain exactly 5 slides.")

    for slide in slides:
        if not slide.get("title") or not slide.get("body"):
            raise ValueError("Each slide needs a title and body.")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(OUTPUT_FILE),
    ]

    print("Rendering 5 animated slides...")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    try:
        assert process.stdin is not None

        for slide_index, slide in enumerate(slides):
            for frame_index in range(FRAMES_PER_SLIDE):
                frame = render_frame(
                    data,
                    slide,
                    slide_index,
                    frame_index,
                )
                process.stdin.write(frame.tobytes())

        process.stdin.close()
        return_code = process.wait()
        error_output = process.stderr.read().decode(
            "utf-8", errors="replace"
        )

        if return_code != 0:
            raise RuntimeError(f"FFmpeg failed: {error_output}")

    except Exception:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise

    print(f"Video created successfully: {OUTPUT_FILE}")
    print(
        f"Duration: {len(slides) * SECONDS_PER_SLIDE} seconds; "
        f"resolution: {WIDTH}x{HEIGHT}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
