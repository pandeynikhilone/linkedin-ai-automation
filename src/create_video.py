import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CONTENT_FILE = ROOT / "content.json"
OUTPUT_FILE = ROOT / "linkedin_video.mp4"
WEBSITE_SCREENSHOT = ROOT / "generated_assets" / "truloop_homepage.png"
PRODUCTS_SCREENSHOT = ROOT / "generated_assets" / "truloop_products.png"
PRODUCT_DETAIL_SCREENSHOT = ROOT / "generated_assets" / "truloop_product_detail.png"
PRODUCT_REVIEWS_SCREENSHOT = ROOT / "generated_assets" / "truloop_product_reviews.png"
SUBMIT_REVIEW_SCREENSHOT = ROOT / "generated_assets" / "truloop_submit_review.png"
ADD_REVIEW_SCREENSHOT = ROOT / "generated_assets" / "truloop_add_review.png"
LOGIN_SCREENSHOT = ROOT / "generated_assets" / "truloop_login.png"
REGISTER_SCREENSHOT = ROOT / "generated_assets" / "truloop_register.png"
PROFILE_SCREENSHOT = ROOT / "generated_assets" / "truloop_profile.png"
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

PAPER = (249, 250, 253)
PAPER_DARK = (238, 241, 249)
WHITE = (255, 255, 255)
INK = (17, 19, 29)
GREEN = (105, 74, 230)
GREEN_DARK = (13, 16, 26)
LIME = (91, 151, 255)
MUTED = (87, 96, 116)
LINE = (220, 225, 236)
TEAL = (53, 143, 236)
CLAY = (157, 88, 235)
OCHRE = (126, 103, 250)
LAVENDER = (239, 235, 255)
PALE_BLUE = (229, 240, 255)

# The topic selects a visual family. The story keeps a consistent signature, but
# each topic gets a different art direction rather than reusing the same skin.
THEMES = [
    {
        "name": "violet editorial",
        "background": (249, 250, 253), "panel": (239, 235, 255), "surface": (255, 255, 255),
        "ink": (17, 19, 29), "muted": (87, 96, 116), "primary": (105, 74, 230),
        "secondary": (53, 143, 236), "accent": (91, 151, 255), "line": (220, 225, 236),
        "dark": (13, 16, 26), "on_dark": (249, 250, 253), "on_dark_muted": (196, 202, 217),
    },
    {
        "name": "blueprint",
        "background": (242, 249, 255), "panel": (222, 239, 252), "surface": (255, 255, 255),
        "ink": (15, 37, 62), "muted": (67, 93, 117), "primary": (0, 104, 173),
        "secondary": (0, 155, 190), "accent": (244, 171, 66), "line": (198, 220, 237),
        "dark": (10, 31, 53), "on_dark": (246, 251, 255), "on_dark_muted": (176, 203, 222),
    },
    {
        "name": "warm notebook",
        "background": (252, 247, 237), "panel": (245, 231, 208), "surface": (255, 253, 248),
        "ink": (44, 34, 27), "muted": (111, 91, 76), "primary": (168, 75, 46),
        "secondary": (52, 111, 97), "accent": (213, 145, 68), "line": (225, 211, 188),
        "dark": (44, 34, 27), "on_dark": (255, 250, 241), "on_dark_muted": (219, 201, 182),
    },
    {
        "name": "dark studio",
        "background": (240, 243, 249), "panel": (225, 230, 241), "surface": (255, 255, 255),
        "ink": (22, 26, 40), "muted": (83, 92, 113), "primary": (133, 103, 250),
        "secondary": (45, 183, 205), "accent": (189, 231, 113), "line": (209, 216, 232),
        "dark": (16, 19, 29), "on_dark": (246, 248, 255), "on_dark_muted": (181, 190, 209),
    },
    {
        "name": "monochrome",
        "background": (250, 250, 248), "panel": (233, 233, 229), "surface": (255, 255, 255),
        "ink": (20, 20, 22), "muted": (90, 90, 94), "primary": (25, 25, 28),
        "secondary": (115, 118, 125), "accent": (236, 100, 72), "line": (220, 220, 216),
        "dark": (19, 20, 23), "on_dark": (252, 252, 250), "on_dark_muted": (192, 194, 198),
    },
    {
        "name": "terminal green",
        "background": (242, 248, 240), "panel": (220, 237, 218), "surface": (253, 255, 251),
        "ink": (22, 45, 27), "muted": (80, 107, 83), "primary": (29, 97, 54),
        "secondary": (43, 143, 93), "accent": (190, 227, 91), "line": (205, 225, 201),
        "dark": (10, 31, 19), "on_dark": (245, 255, 241), "on_dark_muted": (177, 205, 175),
    },
]

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


def centered_label(draw, text, box, font, fill, max_lines=2):
    x1, y1, x2, y2 = box
    lines = wrap_text(draw, text, font, max(20, x2 - x1 - 20))[:max_lines]
    line_heights = []
    for line in lines:
        bounds = draw.textbbox((0, 0), line, font=font)
        line_heights.append(max(1, bounds[3] - bounds[1]))
    total_height = sum(line_heights) + 4 * max(0, len(lines) - 1)
    y = y1 + max(0, (y2 - y1 - total_height) // 2)
    for line, height in zip(lines, line_heights):
        bounds = draw.textbbox((0, 0), line, font=font)
        x = x1 + max(0, (x2 - x1 - (bounds[2] - bounds[0])) // 2)
        draw.text((x, y), line, font=font, fill=fill)
        y += height + 4


def draw_visual(draw, slide, box, slide_index, theme):
    """Draw a topic labelled diagram. Avoid unlabelled filler art and invented metrics."""
    kind = slide.get("visual_type", "flow")
    labels = [str(value).strip() for value in slide.get("visual_labels", []) if str(value).strip()]
    labels = labels[:4] or ["Input", "Process", "Output"]
    layout = slide.get("layout", "evidence")
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    ink, muted = theme["ink"], theme["muted"]
    primary, secondary, accent = theme["primary"], theme["secondary"], theme["accent"]
    line, panel, surface = theme["line"], theme["panel"], theme["surface"]

    # Evidence and hero layouts get a clean source frame. Process layouts remain open.
    if layout != "process":
        draw.rounded_rectangle(box, radius=28, fill=surface, outline=line, width=2)
        inset = 24
    else:
        inset = 6
    left, right = x1 + inset, x2 - inset
    top, bottom = y1 + inset, y2 - inset
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

    if kind == "chart":
        # A chart vocabulary explainer, not invented business data.
        count = min(4, max(3, len(labels)))
        gap = 14
        card_w = (right - left - gap * (count - 1)) // count
        card_top = top + 22
        card_bottom = bottom - 32
        for index in range(count):
            bx = left + index * (card_w + gap)
            draw.rounded_rectangle((bx, card_top, bx + card_w, card_bottom), radius=18, fill=panel)
            base_y = card_bottom - 82
            chart_x = bx + 24
            chart_right = bx + card_w - 24
            chart_top = card_top + 28
            draw.line((chart_x, chart_top, chart_x, base_y), fill=muted, width=3)
            draw.line((chart_x, base_y, chart_right, base_y), fill=muted, width=3)
            bar_w = max(12, min(26, (chart_right - chart_x) // 5))
            heights = [48, 72, 56, 86]
            for b_index, h in enumerate(heights[:3]):
                bx2 = chart_x + 18 + b_index * (bar_w + 9)
                if bx2 + bar_w < chart_right:
                    draw.rounded_rectangle((bx2, base_y - h, bx2 + bar_w, base_y), radius=5,
                                           fill=[primary, secondary, accent][b_index])
            centered_label(draw, labels[index % len(labels)], (bx + 8, card_bottom - 72, bx + card_w - 8, card_bottom - 12),
                           load_font(17, True), ink, max_lines=2)

    elif kind == "flow":
        count = min(4, max(3, len(labels)))
        gap = 26
        node_w = (right - left - gap * (count - 1)) // count
        node_y = cy - 72
        node_h = 144
        colors = [panel, surface, panel, surface]
        for i in range(count):
            nx = left + i * (node_w + gap)
            draw.rounded_rectangle((nx, node_y, nx + node_w, node_y + node_h), radius=22,
                                   fill=colors[i % len(colors)], outline=line, width=2)
            draw.ellipse((nx + 16, node_y + 16, nx + 48, node_y + 48),
                         fill=[primary, secondary, accent][i % 3])
            draw.text((nx + 18, node_y + 18), str(i + 1), font=load_font(17, True), fill=surface)
            centered_label(draw, labels[i % len(labels)], (nx + 8, node_y + 52, nx + node_w - 8, node_y + node_h - 8),
                           load_font(20, True), ink, max_lines=3)
            if i < count - 1:
                draw_arrow(draw, (nx + node_w + 3, cy), (nx + node_w + gap - 5, cy), primary, width=4)

    elif kind == "code":
        # Labelled implementation areas instead of fake code or decorative syntax bars.
        draw.rounded_rectangle((left + 12, top + 10, right - 12, bottom - 10), radius=24, fill=theme["dark"])
        for i, color in enumerate([primary, secondary, accent]):
            draw.ellipse((left + 34 + i * 28, top + 30, left + 48 + i * 28, top + 44), fill=color)
        header = labels[0] if labels else slide.get("title", "Implementation detail")
        draw.text((left + 34, top + 70), header[:42], font=load_font(24, True), fill=theme["on_dark"])
        draw.line((left + 34, top + 116, right - 34, top + 116), fill=(70, 78, 100), width=2)
        content_labels = labels[1:] or ["Input handling", "Core logic", "Response"]
        row_h = max(56, min(88, (bottom - top - 160) // max(1, len(content_labels))))
        for i, label in enumerate(content_labels):
            yy = top + 143 + i * row_h
            draw.rounded_rectangle((left + 34, yy, left + 74, yy + 36), radius=10,
                                   fill=[primary, secondary, accent][i % 3])
            draw.text((left + 46, yy + 7), f"{i + 1}", font=load_font(17, True), fill=surface)
            draw.text((left + 94, yy + 3), label[:44], font=load_font(22, True), fill=theme["on_dark"])
            draw.line((left + 94, yy + 39, right - 34, yy + 39), fill=(53, 61, 82), width=2)

    elif kind == "database":
        cylinder_x = left + max(110, width // 5)
        cylinder_y = cy
        rx, ry = 90, 30
        for i, color in enumerate([primary, secondary, accent]):
            yy = cylinder_y - 92 + i * 60
            draw.rectangle((cylinder_x - rx, yy + ry, cylinder_x + rx, yy + 60), fill=color)
            draw.ellipse((cylinder_x - rx, yy, cylinder_x + rx, yy + 2 * ry), fill=color, outline=ink, width=2)
            draw.arc((cylinder_x - rx, yy + 28, cylinder_x + rx, yy + 2 * ry + 34), 0, 180, fill=ink, width=2)
        text_x = left + width * 0.43
        label_h = max(54, min(76, (height - 36) // max(1, len(labels))))
        for i, label in enumerate(labels):
            yy = top + 22 + i * (label_h + 14)
            draw.rounded_rectangle((text_x, yy, right - 20, yy + label_h), radius=16, fill=panel, outline=line, width=1)
            draw.text((text_x + 20, yy + 12), label[:32], font=load_font(21, True), fill=ink)

    elif kind in {"form", "checklist"}:
        row_h = max(54, min(86, (height - 58) // max(1, len(labels))))
        total_h = row_h * len(labels) + 14 * (len(labels) - 1)
        row_top = cy - total_h // 2
        for i, label in enumerate(labels):
            yy = row_top + i * (row_h + 14)
            draw.rounded_rectangle((left + 18, yy, right - 18, yy + row_h), radius=16, fill=panel if i % 2 == 0 else surface, outline=line, width=1)
            mx, my = left + 48, yy + row_h // 2
            if kind == "checklist":
                draw.rounded_rectangle((mx - 14, my - 14, mx + 14, my + 14), radius=6, outline=secondary, width=3)
                draw.line((mx - 7, my, mx - 1, my + 7, mx + 11, my - 9), fill=secondary, width=3)
            else:
                draw.ellipse((mx - 11, my - 11, mx + 11, my + 11), fill=primary)
            draw.text((left + 78, yy + max(8, (row_h - 28) // 2)), label[:48], font=load_font(22, True), fill=ink)

    elif kind == "git":
        points = [(left + 95, cy - 90), (cx - 20, cy + 10), (right - 95, cy - 100), (right - 95, cy + 105)]
        draw.line((points[0], points[1], points[2]), fill=primary, width=7)
        draw.line((points[1], points[3]), fill=secondary, width=7)
        for i, point in enumerate(points):
            px, py = point
            draw.ellipse((px - 24, py - 24, px + 24, py + 24), fill=[primary, secondary, accent, primary][i], outline=surface, width=3)
            label = labels[i % len(labels)]
            centered_label(draw, label, (px - 105, py + 34, px + 105, py + 94), load_font(17, True), ink, max_lines=2)

    elif kind == "stack":
        layer_h = max(52, min(76, (height - 45) // max(1, len(labels))))
        total_h = len(labels) * layer_h + (len(labels) - 1) * 12
        layer_top = cy - total_h // 2
        for i, label in enumerate(labels):
            inset_x = i * 18
            yy = layer_top + i * (layer_h + 12)
            draw.rounded_rectangle((left + 70 + inset_x, yy, right - 70 - inset_x, yy + layer_h), radius=16,
                                   fill=[panel, surface][i % 2], outline=[primary, secondary, accent][i % 3], width=3)
            centered_label(draw, label, (left + 90 + inset_x, yy + 4, right - 90 - inset_x, yy + layer_h - 4),
                           load_font(22, True), ink, max_lines=2)

    elif kind == "product":
        count = min(3, max(2, len(labels)))
        gap = 18
        card_w = (right - left - gap * (count - 1)) // count
        for i in range(count):
            bx = left + i * (card_w + gap)
            draw.rounded_rectangle((bx, top + 26, bx + card_w, bottom - 26), radius=24,
                                   fill=surface, outline=line, width=2)
            draw.ellipse((bx + card_w // 2 - 36, top + 58, bx + card_w // 2 + 36, top + 130),
                         fill=[panel, theme["background"]][i % 2], outline=[primary, secondary, accent][i % 3], width=3)
            centered_label(draw, labels[i % len(labels)], (bx + 14, top + 145, bx + card_w - 14, bottom - 40),
                           load_font(20, True), ink, max_lines=3)

    else:
        # Learning and architecture use labelled milestones, not ornamental nodes.
        count = min(4, max(3, len(labels)))
        gap = 18
        card_w = (right - left - gap * (count - 1)) // count
        for i in range(count):
            bx = left + i * (card_w + gap)
            draw.rounded_rectangle((bx, top + 34, bx + card_w, bottom - 34), radius=22,
                                   fill=panel if i % 2 == 0 else surface, outline=line, width=2)
            draw.ellipse((bx + 20, top + 58, bx + 60, top + 98), fill=[primary, secondary, accent][i % 3])
            draw.text((bx + 32, top + 66), str(i + 1), font=load_font(18, True), fill=surface)
            centered_label(draw, labels[i % len(labels)], (bx + 10, top + 120, bx + card_w - 10, bottom - 44),
                           load_font(19, True), ink, max_lines=3)


def draw_website_visual(canvas, draw, box, slide, theme, topic):
    """Use the most relevant genuine screen from the deployed site, never a recreated UI."""
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=24, fill=theme["surface"], outline=theme["line"], width=2)

    context = (str(topic) + " " + str(slide.get("title", "")) + " " + str(slide.get("body", ""))).casefold()
    if any(term in context for term in ("submit review", "review submission", "review form", "proof validation", "receipt", "purchase date", "required fields")):
        candidates = [SUBMIT_REVIEW_SCREENSHOT, ADD_REVIEW_SCREENSHOT, PRODUCT_REVIEWS_SCREENSHOT, PRODUCT_DETAIL_SCREENSHOT, WEBSITE_SCREENSHOT]
    elif any(term in context for term in ("product review", "review flow", "rating", "reviews", "average rating", "review data")):
        candidates = [PRODUCT_REVIEWS_SCREENSHOT, PRODUCT_DETAIL_SCREENSHOT, SUBMIT_REVIEW_SCREENSHOT, PRODUCTS_SCREENSHOT, WEBSITE_SCREENSHOT]
    elif any(term in context for term in ("catalog", "catalogue", "listing", "browse products", "product list", "product browsing")):
        candidates = [PRODUCTS_SCREENSHOT, PRODUCT_DETAIL_SCREENSHOT, WEBSITE_SCREENSHOT]
    elif any(term in context for term in ("product detail", "specification", "product page", "detail page", "product information")):
        candidates = [PRODUCT_DETAIL_SCREENSHOT, PRODUCT_REVIEWS_SCREENSHOT, PRODUCTS_SCREENSHOT, WEBSITE_SCREENSHOT]
    elif any(term in context for term in ("login", "register", "authentication", "profile", "jwt", "bcrypt")):
        candidates = [LOGIN_SCREENSHOT, REGISTER_SCREENSHOT, PROFILE_SCREENSHOT, WEBSITE_SCREENSHOT]
    elif any(term in context for term in ("frontend", "navigation", "component", "interface", "homepage", "behind the ui")):
        candidates = [WEBSITE_SCREENSHOT, PRODUCTS_SCREENSHOT, PRODUCT_DETAIL_SCREENSHOT]
    else:
        # Stable topic-based rotation avoids repeatedly selecting the homepage by default.
        alternatives = [WEBSITE_SCREENSHOT, PRODUCTS_SCREENSHOT, PRODUCT_DETAIL_SCREENSHOT, PRODUCT_REVIEWS_SCREENSHOT]
        seed = sum((position + 1) * ord(char) for position, char in enumerate(str(topic)))
        candidates = alternatives[seed % len(alternatives):] + alternatives[:seed % len(alternatives)]
    screenshot_path = next((path for path in candidates if path.is_file()), None)
    if screenshot_path is None:
        return False

    with Image.open(screenshot_path) as source:
        screenshot = source.convert("RGB")
        max_size = (max(1, x2 - x1 - 36), max(1, y2 - y1 - 36))
        fitted = ImageOps.contain(screenshot, max_size, method=Image.Resampling.LANCZOS)
        px = x1 + (x2 - x1 - fitted.width) // 2
        py = y1 + (y2 - y1 - fitted.height) // 2
        canvas.paste(fitted, (px, py))
        draw.rounded_rectangle((px, py, px + fitted.width - 1, py + fitted.height - 1),
                               radius=10, outline=theme["ink"], width=2)
    return True


def theme_for_topic(topic):
    """Stable theme rotation so adjacent topics are not dressed identically."""
    seed = sum((index + 1) * ord(char) for index, char in enumerate(str(topic)))
    return THEMES[seed % len(THEMES)]


def draw_brand_line(draw, slide_number, total, theme, light=False):
    foreground = theme["on_dark"] if light else theme["muted"]
    accent = theme["accent"]
    draw.ellipse((74, 60, 98, 84), fill=accent)
    draw.text((112, 56), "NIKHIL PANDEY  /  BUILD NOTES", font=load_font(18, True), fill=foreground)
    pill = (WIDTH - 150, 48, WIDTH - 72, 94)
    draw.rounded_rectangle(pill, radius=22, fill=theme["primary"])
    centered_label(draw, f"{slide_number:02d} / {total:02d}", pill, load_font(17, True), theme["surface"], max_lines=1)


def draw_layout_visual(image, draw, slide, box, index, theme, topic):
    kind = slide.get("visual_type", "flow")
    if kind == "website":
        if draw_website_visual(image, draw, box, slide, theme, topic):
            return
        print("WARNING: No genuine TruLoop screenshot was available; using a labelled architecture diagram.")
        fallback = dict(slide)
        fallback["visual_type"] = "flow"
        draw_visual(draw, fallback, box, index, theme)
        return
    draw_visual(draw, slide, box, index, theme)


def render_slide(slide, index, total, topic, output_path):
    """Compose each slide with a different layout and rotate the art direction by topic."""
    theme = theme_for_topic(topic)
    layout = slide.get("layout", DEFAULT_SLIDE_LAYOUTS[min(index, len(DEFAULT_SLIDE_LAYOUTS) - 1)])
    dark_bg = theme["dark"]
    light_ink = theme["ink"]
    muted = theme["muted"]
    title = clean_title(slide.get("title", ""))
    body = str(slide.get("body", "")).strip()
    image = Image.new("RGB", (WIDTH, HEIGHT), theme["background"])
    draw = ImageDraw.Draw(image)

    # Subtle background detail changes by art direction but never competes with the text.
    if theme["name"] == "blueprint":
        for x in range(36, WIDTH, 56):
            draw.line((x, 0, x, HEIGHT), fill=(232, 241, 249), width=1)
        for y in range(20, HEIGHT, 56):
            draw.line((0, y, WIDTH, y), fill=(232, 241, 249), width=1)
    elif theme["name"] == "warm notebook":
        for y in range(120, HEIGHT, 72):
            draw.line((56, y, WIDTH - 56, y), fill=(246, 238, 223), width=1)
    elif theme["name"] == "dark studio":
        draw.ellipse((WIDTH - 360, -170, WIDTH + 120, 320), fill=(32, 39, 59))
        draw.arc((WIDTH - 430, -240, WIDTH + 20, 390), 15, 205, fill=theme["primary"], width=3)
    elif theme["name"] == "monochrome":
        for dot_x in range(WIDTH - 230, WIDTH - 65, 24):
            for dot_y in range(145, 300, 24):
                draw.ellipse((dot_x, dot_y, dot_x + 3, dot_y + 3), fill=(218, 218, 214))
    elif theme["name"] == "terminal green":
        for dot_x in range(WIDTH - 250, WIDTH - 65, 22):
            for dot_y in range(135, 300, 22):
                draw.rounded_rectangle((dot_x, dot_y, dot_x + 5, dot_y + 5), radius=2, fill=(211, 230, 205))

    draw_brand_line(draw, index + 1, total, theme, light=(layout in {"hero", "closing"}))

    if layout == "hero":
        image.paste(dark_bg, (0, 0, WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        draw_brand_line(draw, index + 1, total, theme, light=True)
        draw.text((76, 150), "PROJECT NOTE  /  WHAT I AM LEARNING", font=load_font(17, True), fill=theme["accent"])
        title_bottom = draw_wrapped(draw, title, (72, 204), load_font(76, True),
                                    theme["on_dark"], WIDTH - 144, line_gap=2, max_lines=2)
        body_top = max(376, title_bottom + 16)
        body_bottom = draw_wrapped(draw, body, (78, body_top), load_font(29),
                                   theme["on_dark_muted"], WIDTH - 156, line_gap=8, max_lines=3)
        visual_top = min(max(body_bottom + 26, 570), 670)
        box = (64, visual_top, WIDTH - 64, 1206)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.text((76, 1260), "BUILD  /  TRACE  /  TEST  /  LEARN", font=load_font(16, True), fill=theme["on_dark_muted"])

    elif layout == "split":
        draw.line((520, 150, 520, 1120), fill=theme["line"], width=3)
        draw.text((76, 151), "THE IDEA", font=load_font(17, True), fill=theme["primary"])
        title_bottom = draw_wrapped(draw, title, (72, 196), load_font(55, True),
                                    light_ink, 398, line_gap=7, max_lines=4)
        body_top = max(470, title_bottom + 24)
        draw_wrapped(draw, body, (78, body_top), load_font(27), muted, 388, line_gap=9, max_lines=6)
        draw.rounded_rectangle((78, 1100, 420, 1112), radius=6, fill=theme["accent"])
        box = (548, 205, 1018, 1060)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.text((78, 1160), "CONTEXT  /  WHY IT MATTERS", font=load_font(15, True), fill=muted)

    elif layout == "evidence":
        draw.text((74, 143), "REAL PROJECT  /  EVIDENCE", font=load_font(17, True), fill=theme["primary"])
        title_bottom = draw_wrapped(draw, title, (72, 188), load_font(58, True),
                                    light_ink, WIDTH - 144, line_gap=5, max_lines=2)
        body_top = max(332, title_bottom + 18)
        body_bottom = draw_wrapped(draw, body, (78, body_top), load_font(27), muted,
                                   WIDTH - 156, line_gap=8, max_lines=3)
        box_top = max(body_bottom + 20, 505)
        box = (64, box_top, WIDTH - 64, 1108)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        chips = slide.get("visual_labels", [])[:4]
        chip_x = 72
        for chip in chips:
            w = min(245, max(120, draw.textbbox((0, 0), chip, font=load_font(16, True))[2] + 34))
            if chip_x + w > WIDTH - 64:
                break
            draw.rounded_rectangle((chip_x, 1152, chip_x + w, 1196), radius=18, fill=theme["panel"])
            centered_label(draw, chip, (chip_x + 4, 1154, chip_x + w - 4, 1194), load_font(16, True), theme["primary"], max_lines=1)
            chip_x += w + 12
        draw.text((74, 1260), "A CLOSER LOOK AT THE IMPLEMENTATION", font=load_font(15, True), fill=muted)

    elif layout == "process":
        draw.text((74, 140), "FOLLOW THE FLOW", font=load_font(17, True), fill=theme["primary"])
        title_bottom = draw_wrapped(draw, title, (72, 184), load_font(58, True),
                                    light_ink, WIDTH - 144, line_gap=6, max_lines=2)
        body_top = max(330, title_bottom + 18)
        draw_wrapped(draw, body, (78, body_top), load_font(27), muted,
                     WIDTH - 156, line_gap=8, max_lines=3)
        box = (54, 455, WIDTH - 54, 1034)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.line((76, 1115, WIDTH - 76, 1115), fill=theme["line"], width=2)
        draw.text((76, 1150), "REQUEST", font=load_font(16, True), fill=theme["primary"])
        draw.text((WIDTH // 2 - 45, 1150), "PROCESS", font=load_font(16, True), fill=theme["secondary"])
        draw.text((WIDTH - 188, 1150), "RESPONSE", font=load_font(16, True), fill=theme["primary"])

    elif layout == "editorial":
        draw.rectangle((0, 0, 290, HEIGHT), fill=dark_bg)
        draw.text((54, 170), f"{index + 1:02d}", font=load_font(86, True), fill=theme["accent"])
        draw_wrapped(draw, "FIELD NOTES", (56, 282), load_font(18, True), theme["on_dark"], 190, line_gap=5, max_lines=2)
        draw_wrapped(draw, title, (332, 150), load_font(55, True), light_ink, 670, line_gap=6, max_lines=4)
        draw_wrapped(draw, body, (338, 415), load_font(27), muted, 640, line_gap=8, max_lines=5)
        box = (330, 700, 1015, 1100)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.text((338, 1172), "OBSERVE  /  EXPLAIN  /  IMPROVE", font=load_font(15, True), fill=theme["primary"])

    elif layout == "detail":
        image.paste(theme["panel"], (0, 0, WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        draw_brand_line(draw, index + 1, total, theme, light=False)
        draw.text((78, 150), "IMPLEMENTATION DETAIL", font=load_font(17, True), fill=theme["primary"])
        title_bottom = draw_wrapped(draw, title, (74, 196), load_font(59, True),
                                    light_ink, WIDTH - 148, line_gap=6, max_lines=2)
        draw_wrapped(draw, body, (80, max(330, title_bottom + 20)), load_font(27), muted,
                     WIDTH - 160, line_gap=8, max_lines=3)
        box = (70, 500, WIDTH - 70, 1100)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.text((78, 1170), "DETAILS MATTER MORE THAN DECORATION", font=load_font(15, True), fill=theme["primary"])

    elif layout == "closing":
        image.paste(dark_bg, (0, 0, WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        draw_brand_line(draw, index + 1, total, theme, light=True)
        draw.text((76, 154), "THE TAKEAWAY", font=load_font(17, True), fill=theme["accent"])
        title_bottom = draw_wrapped(draw, title, (72, 205), load_font(68, True),
                                    theme["on_dark"], WIDTH - 144, line_gap=4, max_lines=3)
        body_top = max(425, title_bottom + 22)
        body_bottom = draw_wrapped(draw, body, (78, body_top), load_font(29),
                                   theme["on_dark_muted"], WIDTH - 156, line_gap=8, max_lines=3)
        # The last scene favours the lesson, so the visual is a compact set of labelled steps.
        box_top = max(body_bottom + 28, 700)
        box = (76, min(box_top, 780), WIDTH - 76, 1050)
        draw_layout_visual(image, draw, slide, box, index, theme, topic)
        draw.line((76, 1145, WIDTH - 76, 1145), fill=(65, 72, 93), width=2)
        draw.text((78, 1181), "REAL PROJECTS  /  CONTINUING TO LEARN IN PUBLIC",
                  font=load_font(15, True), fill=theme["on_dark_muted"])

    else:
        # Unknown layouts are rendered as an editorial note, never as a duplicate default slide.
        draw_wrapped(draw, title, (78, 180), load_font(60, True), light_ink, WIDTH - 156, max_lines=3)
        draw_wrapped(draw, body, (82, 360), load_font(29), muted, WIDTH - 164, max_lines=4)
        draw_layout_visual(image, draw, slide, (70, 620, WIDTH - 70, 1120), index, theme, topic)

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
