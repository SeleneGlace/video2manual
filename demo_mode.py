"""
Demo mode: runs the full pipeline with mock LLM data.
No API key required — shows you exactly what the real output looks like.

Usage: python demo_mode.py
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# ---------- Fake platform UI generator ----------

def make_fake_frame(width=1280, height=720, scene="list"):
    """Generate a realistic-looking fake ad platform screenshot."""
    img = Image.new("RGB", (width, height), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    # Sidebar
    draw.rectangle([0, 0, 200, height], fill=(30, 41, 59))
    nav_items = ["首页", "素材管理", "投放计划", "流量策略", "数据报表", "系统设置"]
    for i, item in enumerate(nav_items):
        y = 80 + i * 50
        if (scene == "list" and item == "素材管理") or \
           (scene in ("new", "form", "submit", "success") and item == "素材管理"):
            draw.rectangle([0, y - 8, 200, y + 32], fill=(59, 130, 246))
        try:
            font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
        except Exception:
            font = ImageFont.load_default()
        draw.text((20, y), item, fill=(203, 213, 225), font=font)

    # Top bar
    draw.rectangle([200, 0, width, 56], fill=(255, 255, 255))
    draw.line([(200, 56), (width, 56)], fill=(226, 232, 240), width=1)
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
        font_small = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 13)
        font_btn = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
    except Exception:
        font_title = font_small = font_btn = ImageFont.load_default()

    if scene == "list":
        draw.text((220, 18), "素材管理", fill=(15, 23, 42), font=font_title)
        # New button (top right)
        draw.rectangle([1080, 12, 1220, 44], fill=(59, 130, 246), width=0)
        draw.rounded_rectangle([1080, 12, 1220, 44], radius=6, fill=(59, 130, 246))
        draw.text((1104, 20), "+ 新建素材", fill=(255, 255, 255), font=font_btn)
        # Table
        draw.rectangle([220, 80, width - 20, 120], fill=(241, 245, 249))
        headers = ["素材ID", "素材名称", "素材类型", "尺寸", "状态", "创建时间", "操作"]
        for j, h in enumerate(headers):
            draw.text((240 + j * 145, 94), h, fill=(71, 85, 105), font=font_small)
        for row in range(5):
            y_row = 130 + row * 50
            fill = (255, 255, 255) if row % 2 == 0 else (248, 250, 252)
            draw.rectangle([220, y_row, width - 20, y_row + 50], fill=fill)
            draw.text((240, y_row + 16), f"MAT-{1001 + row}", fill=(100, 116, 139), font=font_small)
            draw.text((385, y_row + 16), f"夏季促销Banner_{row + 1}", fill=(15, 23, 42), font=font_small)
            draw.text((530, y_row + 16), "图片", fill=(100, 116, 139), font=font_small)
            draw.text((675, y_row + 16), "1200x628", fill=(100, 116, 139), font=font_small)
            status_color = (22, 163, 74) if row != 2 else (234, 88, 12)
            status_text = "已审核" if row != 2 else "审核中"
            draw.rectangle([800, y_row + 10, 860, y_row + 36], fill=status_color)
            draw.text((808, y_row + 16), status_text, fill=(255, 255, 255), font=font_small)

    elif scene == "new":
        draw.text((220, 18), "素材管理", fill=(15, 23, 42), font=font_title)
        draw.rounded_rectangle([1080, 12, 1220, 44], radius=6, fill=(59, 130, 246))
        draw.text((1104, 20), "+ 新建素材", fill=(255, 255, 255), font=font_btn)
        # Modal overlay
        draw.rectangle([0, 0, width, height], fill=(0, 0, 0, 128))
        draw.rounded_rectangle([340, 160, 940, 580], radius=12, fill=(255, 255, 255))
        draw.text((380, 188), "新建素材", fill=(15, 23, 42), font=font_title)
        draw.line([(340, 220), (940, 220)], fill=(226, 232, 240))
        draw.text((370, 236), "素材类型", fill=(71, 85, 105), font=font_small)
        # Type selector
        types = ["图片", "视频", "HTML5", "原生"]
        for k, t in enumerate(types):
            bx = 370 + k * 130
            color = (59, 130, 246) if k == 0 else (241, 245, 249)
            text_color = (255, 255, 255) if k == 0 else (71, 85, 105)
            draw.rounded_rectangle([bx, 264, bx + 110, 298], radius=6, fill=color)
            draw.text((bx + 36, 273), t, fill=text_color, font=font_small)
        # Close button
        draw.text((900, 185), "✕", fill=(100, 116, 139), font=font_title)

    elif scene == "form":
        draw.text((220, 18), "新建素材", fill=(15, 23, 42), font=font_title)
        # Breadcrumb
        draw.text((220, 68), "素材管理  >  新建素材", fill=(100, 116, 139), font=font_small)
        # Form card
        draw.rounded_rectangle([220, 90, width - 20, height - 40], radius=8, fill=(255, 255, 255))
        draw.text((250, 116), "基本信息", fill=(15, 23, 42), font=font_title)
        fields = [
            ("素材名称 *", "请输入素材名称，如：夏季大促-Banner-1200x628", 160),
            ("素材描述", "请输入素材描述（选填）", 260),
            ("投放渠道 *", "请选择投放渠道", 360),
        ]
        for label, placeholder, fy in fields:
            draw.text((250, fy), label, fill=(71, 85, 105), font=font_small)
            draw.rounded_rectangle([250, fy + 24, 900, fy + 54], radius=4,
                                  fill=(248, 250, 252), outline=(226, 232, 240))
            draw.text((264, fy + 34), placeholder, fill=(203, 213, 225), font=font_small)
        # Upload area
        draw.text((250, 456), "素材文件 *", fill=(71, 85, 105), font=font_small)
        draw.rounded_rectangle([250, 480, 900, 600], radius=8, fill=(239, 246, 255),
                              outline=(147, 197, 253))
        draw.text((500, 520), "点击或拖拽上传素材文件", fill=(59, 130, 246), font=font_btn)
        draw.text((490, 548), "支持 JPG / PNG / GIF，最大 10MB", fill=(148, 163, 184), font=font_small)
        # Submit button
        draw.rounded_rectangle([250, 630, 420, 666], radius=6, fill=(59, 130, 246))
        draw.text((290, 640), "提交审核", fill=(255, 255, 255), font=font_btn)
        draw.rounded_rectangle([440, 630, 580, 666], radius=6, fill=(241, 245, 249))
        draw.text((488, 640), "取消", fill=(71, 85, 105), font=font_btn)

    elif scene == "success":
        draw.text((220, 18), "素材管理", fill=(15, 23, 42), font=font_title)
        # Success toast
        draw.rounded_rectangle([880, 70, 1240, 116], radius=8, fill=(240, 253, 244),
                              outline=(187, 247, 208))
        draw.text((900, 86), "✓  素材提交成功，等待审核中", fill=(22, 163, 74), font=font_small)
        # Back to list with one item highlighted
        draw.text((220, 68), "素材管理  >  新建完成", fill=(100, 116, 139), font=font_small)
        draw.rectangle([220, 80, width - 20, 120], fill=(241, 245, 249))
        headers = ["素材ID", "素材名称", "素材类型", "尺寸", "状态", "创建时间", "操作"]
        for j, h in enumerate(headers):
            draw.text((240 + j * 145, 94), h, fill=(71, 85, 105), font=font_small)
        # New row highlighted
        draw.rectangle([220, 130, width - 20, 180], fill=(239, 246, 255), outline=(147, 197, 253))
        draw.text((240, 148), "MAT-1006", fill=(59, 130, 246), font=font_small)
        draw.text((385, 148), "夏季大促-Banner-1200x628", fill=(15, 23, 42), font=font_small)
        draw.text((530, 148), "图片", fill=(100, 116, 139), font=font_small)
        draw.text((675, 148), "1200x628", fill=(100, 116, 139), font=font_small)
        draw.rounded_rectangle([800, 140, 868, 168], radius=4, fill=(234, 88, 12))
        draw.text((808, 148), "审核中", fill=(255, 255, 255), font=font_small)

    return img


# ---------- Mock LLM step data ----------

MOCK_STEP_DATA = {
    "title": "如何新建广告素材",
    "summary": "从素材管理列表进入新建流程，填写素材基本信息并提交审核，共 4 步",
    "selected_frame_indices": [0, 1, 2, 3],
    "steps": [
        {
            "step_number": 1,
            "frame_index": 0,
            "page_name": "素材管理列表页",
            "action_description": "在左侧导航栏点击【素材管理】，进入素材列表页面。点击页面右上角的【+ 新建素材】蓝色按钮，开始创建新素材。",
            "highlight_regions": [
                {
                    "type": "rectangle",
                    "label": "点击新建素材",
                    "style": "primary_action",
                    "bbox_pct": [84.4, 1.7, 11.0, 4.4]
                }
            ],
            "tips": None
        },
        {
            "step_number": 2,
            "frame_index": 1,
            "page_name": "选择素材类型",
            "action_description": "在弹出的对话框中，选择素材类型。根据投放需求选择对应类型（图片/视频/HTML5/原生），本示例选择【图片】类型。",
            "highlight_regions": [
                {
                    "type": "rectangle",
                    "label": "选择素材类型",
                    "style": "primary_action",
                    "bbox_pct": [28.9, 36.7, 45.3, 9.4]
                },
                {
                    "type": "rectangle",
                    "label": "关闭弹窗",
                    "style": "reference",
                    "bbox_pct": [70.0, 25.7, 2.8, 3.9]
                }
            ],
            "tips": "选择素材类型后不可更改，请根据投放渠道的格式要求选择正确的类型"
        },
        {
            "step_number": 3,
            "frame_index": 2,
            "page_name": "填写素材基本信息",
            "action_description": "在素材创建表单中，依次填写「素材名称」（必填）、「素材描述」（选填）、「投放渠道」（必填），然后在上传区域点击或拖拽上传素材图片文件。",
            "highlight_regions": [
                {
                    "type": "rectangle",
                    "label": "填写素材名称（必填）",
                    "style": "input_field",
                    "bbox_pct": [19.5, 22.2, 51.6, 7.2]
                },
                {
                    "type": "rectangle",
                    "label": "上传素材文件",
                    "style": "primary_action",
                    "bbox_pct": [19.5, 66.7, 51.6, 16.7]
                },
                {
                    "type": "rectangle",
                    "label": "提交审核",
                    "style": "reference",
                    "bbox_pct": [19.5, 87.5, 13.3, 5.0]
                }
            ],
            "tips": "素材名称建议按照「活动-尺寸-版本」格式命名，便于后续检索，例如：夏季大促-Banner-1200x628"
        },
        {
            "step_number": 4,
            "frame_index": 3,
            "page_name": "提交成功确认",
            "action_description": "填写完成后点击【提交审核】按钮，页面右上角出现绿色成功提示「✓ 素材提交成功，等待审核中」，素材列表中新增一条状态为「审核中」的素材记录，说明提交成功。",
            "highlight_regions": [
                {
                    "type": "rectangle",
                    "label": "提交成功提示",
                    "style": "primary_action",
                    "bbox_pct": [68.8, 9.7, 28.1, 6.4]
                },
                {
                    "type": "rectangle",
                    "label": "新建的素材记录",
                    "style": "reference",
                    "bbox_pct": [17.2, 18.1, 80.5, 6.9]
                }
            ],
            "tips": None
        }
    ]
}


def run_demo():
    """Run the full pipeline with mock data and show output."""
    import tempfile, shutil

    print("=" * 60)
    print("  Video2Manual — Demo Mode（无需 API Key）")
    print("=" * 60)
    print()

    output_dir = Path("./output/demo")
    work_dir = output_dir / "_work"
    annotated_dir = work_dir / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1+2: Generate fake frames (simulating scene detection output)
    print("[Stage 1/5] 生成模拟平台截图...")
    scenes = ["list", "new", "form", "success"]
    fake_frames = []
    frames_dir = work_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, scene in enumerate(scenes):
        img = make_fake_frame(scene=scene)
        path = str(frames_dir / f"frame_{i:04d}.png")
        img.save(path)
        fake_frames.append(path)
    print(f"  ✓ 生成 {len(fake_frames)} 张模拟截图")

    print("[Stage 2/5] 场景检测（模拟：4 个关键帧）...")
    print(f"  ✓ 检测到 4 个场景变化帧")

    print("[Stage 3/5] AI 语义分析（Demo 模式：使用预设数据）...")
    step_data = MOCK_STEP_DATA
    print(f"  ✓ 识别出 {len(step_data['steps'])} 个操作步骤")
    print(f"  ✓ 手册标题：{step_data['title']}")

    # Stage 4: Annotate
    print("[Stage 4/5] 为截图添加标注...")
    sys.path.insert(0, str(Path(__file__).parent))
    from pipeline.image_annotator import annotate_frame, create_flow_overview

    annotated_paths = []
    for i, step in enumerate(step_data["steps"]):
        frame_path = fake_frames[step["frame_index"]]
        out_path = str(annotated_dir / f"step_{i + 1:02d}.png")
        result = annotate_frame(
            frame_path=frame_path,
            highlight_regions=step.get("highlight_regions", []),
            step_number=step["step_number"],
            output_path=out_path,
        )
        annotated_paths.append(result)
        print(f"  ✓ 步骤 {i + 1} 标注完成")

    # Flow overview
    step_titles = [s["page_name"] for s in step_data["steps"]]
    flow_path = str(annotated_dir / "flow_overview.png")
    create_flow_overview(annotated_paths, step_titles, flow_path)
    print(f"  ✓ 流程总览图生成完成")

    # Stage 5: Assemble markdown
    print("[Stage 5/5] 组装 Markdown 操作手册...")
    from pipeline.doc_assembler import assemble_markdown
    md_path = assemble_markdown(
        step_data=step_data,
        annotated_image_paths=annotated_paths,
        flow_overview_path=flow_path,
        output_dir=str(output_dir / "manual"),
    )

    # Clean work dir
    shutil.rmtree(str(work_dir), ignore_errors=True)

    print()
    print("=" * 60)
    print(f"  🎉 Demo 完成！")
    print(f"  📄 Markdown：{md_path}")
    print(f"  🖼️  标注截图：{Path(md_path).parent / 'images'}")
    print("=" * 60)

    # Open output folder
    import subprocess
    subprocess.run(["open", str(Path(md_path).parent)], check=False)

    # Show a preview of the markdown
    print("\n--- Markdown 预览（前 50 行）---\n")
    lines = Path(md_path).read_text(encoding="utf-8").split("\n")
    print("\n".join(lines[:50]))

    return md_path


if __name__ == "__main__":
    run_demo()
