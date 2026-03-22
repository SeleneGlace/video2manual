"""
CV-based UI element detection for more accurate annotation positioning.
Uses color segmentation + contour detection to find buttons and interactive areas.
"""

import cv2
import numpy as np
from pathlib import Path


def find_buttons_by_color(img_bgr, target_colors):
    """
    Find rectangular UI elements matching a target color range.
    Returns list of (x, y, w, h) in pixels.
    """
    results = []
    for (lower, upper) in target_colors:
        lower = np.array(lower, dtype=np.uint8)
        upper = np.array(upper, dtype=np.uint8)
        mask = cv2.inRange(img_bgr, lower, upper)
        # Clean up noise
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            # Filter: must be button-sized (not tiny noise, not full screen)
            img_area = img_bgr.shape[0] * img_bgr.shape[1]
            if 400 < area < img_area * 0.15 and w > 20 and h > 10:
                results.append((x, y, w, h))
    return results


def find_dialog_region(img_bgr):
    """
    Find the main modal dialog region (white card on dimmed background).
    Returns (x, y, w, h) or None.
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Look for large white rectangles (dialogs are usually white)
    _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    kernel = np.ones((20, 20), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        # Dialog should be 20-70% of screen
        if 0.2 * w * h < area < 0.7 * w * h and area > best_area:
            best = (x, y, cw, ch)
            best_area = area

    return best


def find_highlighted_row(img_bgr):
    """
    Find light blue/teal highlighted rows (newly created items, selected rows).
    Returns (x, y, w, h) or None.
    """
    # Light blue highlight colors (Feishu style)
    lower = np.array([200, 225, 235], dtype=np.uint8)  # light blue-ish
    upper = np.array([235, 245, 255], dtype=np.uint8)
    mask = cv2.inRange(img_bgr, lower, upper)

    kernel = np.ones((5, 40), np.uint8)  # horizontal kernel - rows are wide
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = img_bgr.shape[:2]
    best = None
    best_area = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        # A row should be wide (>30% of width) and not too tall
        if cw > w * 0.3 and 15 < ch < 80 and area > best_area:
            best = (x, y, cw, ch)
            best_area = area
    return best


def find_toast_notification(img_bgr):
    """
    Find success/error toast notifications (green/red rounded rect near top).
    Returns (x, y, w, h) or None.
    """
    h, w = img_bgr.shape[:2]
    top_region = img_bgr[:int(h * 0.25), :]  # top 25% of screen

    # Green success toast
    lower = np.array([190, 240, 200], dtype=np.uint8)
    upper = np.array([230, 255, 230], dtype=np.uint8)
    mask = cv2.inRange(top_region, lower, upper)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if 2000 < area < w * h * 0.1 and cw > 100 and area > best_area:
            best = (x, y, cw, ch)
            best_area = area
    return best


def find_primary_buttons(img_bgr):
    """
    Find blue primary action buttons (Feishu blue: ~#3b82f6 / #1677ff style).
    Returns list of (x, y, w, h).
    """
    # Feishu/Lark primary blue in BGR
    color_ranges = [
        ([180, 100, 40], [255, 160, 80]),   # blue range
        ([160, 80, 20], [220, 130, 60]),     # darker blue
    ]
    return find_buttons_by_color(img_bgr, color_ranges)


def px_to_pct(x, y, w, h, img_w, img_h, padding=2):
    """Convert pixel coords to percentage with small padding."""
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(img_w - x, w + padding * 2)
    h = min(img_h - y, h + padding * 2)
    return [
        round(x / img_w * 100, 1),
        round(y / img_h * 100, 1),
        round(w / img_w * 100, 1),
        round(h / img_h * 100, 1),
    ]


def detect_regions_for_frame(frame_path: str, scene_hint: str) -> list:
    """
    Auto-detect annotation regions for a frame based on scene type hint.

    scene_hint: 'list_page' | 'dialog' | 'success_toast' | 'result_list'
    Returns list of region dicts compatible with image_annotator.
    """
    img = cv2.imread(frame_path)
    if img is None:
        return []
    ih, iw = img.shape[:2]
    regions = []

    if scene_hint == 'dialog':
        # Find the dialog box
        dialog = find_dialog_region(img)

        # Find blue primary buttons (创建/确认)
        buttons = find_primary_buttons(img)
        # Sort by size descending, take the biggest one (likely the primary CTA)
        buttons.sort(key=lambda b: b[2] * b[3], reverse=True)

        if dialog:
            dx, dy, dw, dh = dialog
            # Input area = top ~15% of dialog
            input_h = int(dh * 0.12)
            regions.append({
                'type': 'rectangle',
                'label': '输入任务标题',
                'style': 'input_field',
                'bbox_pct': px_to_pct(dx, dy, dw, input_h, iw, ih),
            })
            # Date selection = next 15% of dialog
            date_y = dy + int(dh * 0.18)
            date_h = int(dh * 0.12)
            regions.append({
                'type': 'rectangle',
                'label': '设置截止时间',
                'style': 'reference',
                'bbox_pct': px_to_pct(dx + 30, date_y, dw - 60, date_h, iw, ih),
            })

        # Primary button (创建)
        for bx, by, bw, bh in buttons[:1]:
            regions.append({
                'type': 'rectangle',
                'label': '点击创建',
                'style': 'primary_action',
                'bbox_pct': px_to_pct(bx, by, bw, bh, iw, ih),
            })

    elif scene_hint == 'success_toast':
        toast = find_toast_notification(img)
        if toast:
            tx, ty, tw, th = toast
            regions.append({
                'type': 'rectangle',
                'label': '创建成功提示',
                'style': 'primary_action',
                'bbox_pct': px_to_pct(tx, ty, tw, th, iw, ih),
            })

    elif scene_hint == 'result_list':
        row = find_highlighted_row(img)
        if row:
            rx, ry, rw, rh = row
            regions.append({
                'type': 'rectangle',
                'label': '新建的任务',
                'style': 'primary_action',
                'bbox_pct': px_to_pct(rx, ry, rw, rh, iw, ih),
            })
        else:
            # Fallback: look for any blue buttons (新建任务 button)
            buttons = find_primary_buttons(img)
            buttons.sort(key=lambda b: b[2] * b[3], reverse=True)
            for bx, by, bw, bh in buttons[:1]:
                regions.append({
                    'type': 'rectangle',
                    'label': '新建任务按钮',
                    'style': 'primary_action',
                    'bbox_pct': px_to_pct(bx, by, bw, bh, iw, ih),
                })

    return regions
