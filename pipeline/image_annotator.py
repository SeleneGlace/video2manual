"""Stage 4: Image annotation engine using Pillow."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os


# Color scheme for different annotation styles
STYLE_CONFIG = {
    "primary_action": {
        "border_color": (220, 38, 38),      # red-600
        "fill_color": (220, 38, 38, 35),    # red with 14% opacity
        "badge_color": (220, 38, 38),
        "text_color": (255, 255, 255),
        "border_width": 3,
        "dash": False,
    },
    "reference": {
        "border_color": (37, 99, 235),      # blue-600
        "fill_color": (37, 99, 235, 20),
        "badge_color": (37, 99, 235),
        "text_color": (255, 255, 255),
        "border_width": 2,
        "dash": True,
    },
    "input_field": {
        "border_color": (22, 163, 74),      # green-600
        "fill_color": (22, 163, 74, 25),
        "badge_color": (22, 163, 74),
        "text_color": (255, 255, 255),
        "border_width": 2,
        "dash": False,
    },
    "warning": {
        "border_color": (234, 88, 12),      # orange-600
        "fill_color": (234, 88, 12, 30),
        "badge_color": (234, 88, 12),
        "text_color": (255, 255, 255),
        "border_width": 3,
        "dash": False,
    },
}


def get_font(size: int, bold: bool = False):
    """Get a font, falling back to default if system fonts unavailable."""
    font_paths = [
        # macOS system fonts with Chinese support
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_rounded_rect(draw, bbox, radius, fill_color, border_color, border_width, dash=False):
    """Draw a rounded rectangle with optional dashed border."""
    x1, y1, x2, y2 = bbox

    # Draw filled rounded rect on overlay
    if fill_color:
        # Pillow's rounded_rectangle (available in Pillow >= 8.2)
        try:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill_color)
        except AttributeError:
            draw.rectangle([x1, y1, x2, y2], fill=fill_color)

    # Draw border
    if not dash:
        try:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius,
                                   outline=border_color, width=border_width)
        except AttributeError:
            draw.rectangle([x1, y1, x2, y2], outline=border_color, width=border_width)
    else:
        # Simple dashed effect: draw short segments
        segments = 20
        perimeter_pts = _rounded_rect_points(x1, y1, x2, y2, radius, segments * 2)
        for i in range(0, len(perimeter_pts) - 1, 2):
            draw.line([perimeter_pts[i], perimeter_pts[i + 1]],
                     fill=border_color, width=border_width)


def _rounded_rect_points(x1, y1, x2, y2, r, n):
    """Approximate perimeter points of a rounded rectangle."""
    import math
    pts = []
    # top edge
    for i in range(n // 4):
        t = i / (n // 4)
        pts.append((x1 + r + t * (x2 - x1 - 2 * r), y1))
    # right edge
    for i in range(n // 4):
        t = i / (n // 4)
        pts.append((x2, y1 + r + t * (y2 - y1 - 2 * r)))
    # bottom edge
    for i in range(n // 4):
        t = i / (n // 4)
        pts.append((x2 - r - t * (x2 - x1 - 2 * r), y2))
    # left edge
    for i in range(n // 4):
        t = i / (n // 4)
        pts.append((x1, y2 - r - t * (y2 - y1 - 2 * r)))
    return pts


def draw_badge(draw, cx, cy, number, color, size=22):
    """Draw a circular badge with a step number."""
    r = size // 2
    # Circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # Number text
    font = get_font(size - 6, bold=True)
    text = str(number)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
    draw.text((cx - tw // 2, cy - th // 2), text, fill=(255, 255, 255), font=font)


def draw_label(draw, x, y, text, bg_color, max_width=200):
    """Draw a small text label with background."""
    font = get_font(13)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    pad = 4
    label_x2 = min(x + tw + pad * 2, x + max_width)
    draw.rectangle([x, y, label_x2, y + th + pad * 2],
                  fill=bg_color)
    draw.text((x + pad, y + pad), text, fill=(255, 255, 255), font=font)


def annotate_frame(
    frame_path: str,
    highlight_regions: list,
    step_number: int,
    output_path: str
) -> str:
    """
    Annotate a frame with highlight regions and step number.
    Returns the output path.
    """
    img = Image.open(frame_path).convert("RGBA")
    width, height = img.size

    # Create overlay for semi-transparent fills
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Top draw layer for solid elements (borders, badges, labels)
    top_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    top_draw = ImageDraw.Draw(top_layer)

    for region_idx, region in enumerate(highlight_regions):
        bbox_pct = region.get("bbox_pct", [])
        if len(bbox_pct) != 4:
            continue

        x_pct, y_pct, w_pct, h_pct = bbox_pct
        x1 = int(x_pct / 100 * width)
        y1 = int(y_pct / 100 * height)
        x2 = int((x_pct + w_pct) / 100 * width)
        y2 = int((y_pct + h_pct) / 100 * height)

        style = region.get("style", "primary_action")
        config = STYLE_CONFIG.get(style, STYLE_CONFIG["primary_action"])

        radius = max(4, min(12, int(min(x2 - x1, y2 - y1) * 0.1)))

        # Draw semi-transparent fill on overlay
        draw_rounded_rect(
            overlay_draw,
            (x1, y1, x2, y2),
            radius=radius,
            fill_color=config["fill_color"],
            border_color=None,
            border_width=0,
        )

        # Draw border on top layer
        draw_rounded_rect(
            top_draw,
            (x1, y1, x2, y2),
            radius=radius,
            fill_color=None,
            border_color=config["border_color"],
            border_width=config["border_width"],
            dash=config["dash"],
        )

        # Draw badge at top-left corner of the region
        badge_cx = x1 + 12
        badge_cy = y1 - 12 if y1 > 24 else y1 + 12
        draw_badge(top_draw, badge_cx, badge_cy, step_number,
                  config["badge_color"], size=24)

        # Draw label below the region (if there's space)
        label = region.get("label", "")
        if label:
            label_y = y2 + 4 if y2 + 30 < height else y1 - 24
            draw_label(top_draw, x1, label_y, label, config["border_color"])

    # Composite: base image + overlay + top layer
    result = Image.alpha_composite(img, overlay)
    result = Image.alpha_composite(result, top_layer)

    # Save as PNG
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.convert("RGB").save(str(output_path), "PNG", optimize=True)

    return str(output_path)


def create_flow_overview(
    annotated_frames: list,
    step_titles: list,
    output_path: str,
    max_width: int = 1600
) -> str:
    """
    Create a horizontal flow overview image connecting all steps with arrows.
    """
    if not annotated_frames:
        return None

    n = len(annotated_frames)

    # Load all frames and compute layout
    images = [Image.open(p).convert("RGB") for p in annotated_frames]

    # Thumbnail each frame to a fixed height
    thumb_height = 220
    thumbs = []
    for img in images:
        ratio = thumb_height / img.height
        new_w = int(img.width * ratio)
        thumbs.append(img.resize((new_w, thumb_height), Image.LANCZOS))

    thumb_w = thumbs[0].width if thumbs else 320
    arrow_w = 50
    label_h = 40
    pad = 20

    total_w = n * thumb_w + (n - 1) * arrow_w + 2 * pad
    total_h = thumb_height + label_h + 2 * pad

    canvas = Image.new("RGB", (total_w, total_h), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)

    font = get_font(14)
    font_small = get_font(12)

    for i, (thumb, title) in enumerate(zip(thumbs, step_titles)):
        x = pad + i * (thumb_w + arrow_w)
        y = pad

        # Paste thumbnail with subtle border
        canvas.paste(thumb, (x, y))

        # Border around thumbnail
        draw.rectangle([x - 1, y - 1, x + thumb_w, y + thumb_height],
                      outline=(203, 213, 225), width=2)

        # Step label below thumbnail
        label = f"步骤{i + 1}"
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            lw = bbox[2] - bbox[0]
        except AttributeError:
            lw, _ = draw.textsize(label, font=font)

        label_x = x + (thumb_w - lw) // 2
        label_y = y + thumb_height + 6
        draw.text((label_x, label_y), label, fill=(71, 85, 105), font=font)

        # Short title below step label
        if title and len(title) > 0:
            short_title = title[:10] + "…" if len(title) > 10 else title
            try:
                bbox = draw.textbbox((0, 0), short_title, font=font_small)
                tw = bbox[2] - bbox[0]
            except AttributeError:
                tw, _ = draw.textsize(short_title, font=font_small)
            draw.text((x + (thumb_w - tw) // 2, label_y + 18),
                     short_title, fill=(100, 116, 139), font=font_small)

        # Draw arrow to next step
        if i < n - 1:
            arrow_x_start = x + thumb_w + 5
            arrow_x_end = x + thumb_w + arrow_w - 5
            arrow_y = pad + thumb_height // 2

            draw.line([(arrow_x_start, arrow_y), (arrow_x_end, arrow_y)],
                     fill=(148, 163, 184), width=2)
            # Arrowhead
            ah = 8
            draw.polygon([
                (arrow_x_end, arrow_y),
                (arrow_x_end - ah, arrow_y - ah // 2),
                (arrow_x_end - ah, arrow_y + ah // 2),
            ], fill=(148, 163, 184))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path), "PNG", optimize=True)

    return str(output_path)
