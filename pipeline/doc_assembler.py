"""Stage 5: Assemble the final Markdown operation manual."""

from pathlib import Path
from datetime import datetime


MARKDOWN_TEMPLATE = """\
# {title}

> 📋 本文档由 **Video2Manual** 自动生成 · 共 {step_count} 步 · {summary}
>
> *生成时间：{generated_at}*

---

{steps_content}

---

## 操作流程总览

{flow_chart}

![操作流程总览]({flow_overview_rel})

"""

STEP_TEMPLATE = """\
## 步骤{step_number}：{page_name}

{action_description}

![步骤{step_number}截图]({image_rel})

{tips_block}---

"""

TIPS_TEMPLATE = """\
> 💡 **注意：** {tips}

"""


def assemble_markdown(
    step_data: dict,
    annotated_image_paths: list,
    flow_overview_path: str,
    output_dir: str,
    platform_context: str = "平台",
) -> str:
    """
    Assemble the final Markdown manual from step data and annotated images.
    Returns the path to the generated Markdown file.
    """
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    steps = step_data.get("steps", [])
    title = step_data.get("title", "操作手册")
    summary = step_data.get("summary", "")

    # Copy annotated images to output/images/ directory
    import shutil
    final_image_paths = []
    for i, src_path in enumerate(annotated_image_paths):
        if src_path and Path(src_path).exists():
            dest = images_dir / f"step_{i + 1:02d}_annotated.png"
            shutil.copy2(src_path, dest)
            final_image_paths.append(dest)
        else:
            final_image_paths.append(None)

    # Copy flow overview
    flow_overview_dest = None
    if flow_overview_path and Path(flow_overview_path).exists():
        flow_overview_dest = images_dir / "flow_overview.png"
        shutil.copy2(flow_overview_path, flow_overview_dest)

    # Build step content
    steps_content_parts = []
    for i, step in enumerate(steps):
        img_path = final_image_paths[i] if i < len(final_image_paths) else None
        img_rel = f"./images/{img_path.name}" if img_path else ""

        tips_block = ""
        if step.get("tips"):
            tips_block = TIPS_TEMPLATE.format(tips=step["tips"])

        step_md = STEP_TEMPLATE.format(
            step_number=step.get("step_number", i + 1),
            page_name=step.get("page_name", f"步骤 {i + 1}"),
            action_description=step.get("action_description", ""),
            image_rel=img_rel,
            tips_block=tips_block,
        )
        steps_content_parts.append(step_md)

    # Build Mermaid flowchart
    flow_chart = _build_mermaid_chart(steps)

    # Build final document
    flow_overview_rel = (
        f"./images/flow_overview.png" if flow_overview_dest else ""
    )
    doc = MARKDOWN_TEMPLATE.format(
        title=title,
        step_count=len(steps),
        summary=summary,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        steps_content="\n".join(steps_content_parts),
        flow_chart=flow_chart,
        flow_overview_rel=flow_overview_rel,
    )

    # Write Markdown file
    safe_title = "".join(c for c in title if c.isalnum() or c in "_ -").strip()[:30]
    md_filename = f"{safe_title or 'manual'}.md"
    md_path = output_dir / md_filename
    md_path.write_text(doc, encoding="utf-8")

    print(f"✅ Manual saved to: {md_path}")
    return str(md_path)


def _build_mermaid_chart(steps: list) -> str:
    """Build a Mermaid flowchart from step data."""
    if not steps:
        return ""

    lines = ["```mermaid", "graph LR"]

    for i, step in enumerate(steps):
        node_id = f"S{i + 1}"
        # Truncate long labels for chart readability
        label = step.get("page_name", f"步骤{i + 1}")
        label = label[:12] + "…" if len(label) > 12 else label
        lines.append(f'    {node_id}["{label}"]')

        if i < len(steps) - 1:
            next_id = f"S{i + 2}"
            # Use action as edge label (truncated)
            action = step.get("action_description", "")
            # Extract a short action verb from the description
            edge_label = _extract_edge_label(action)
            lines.append(f'    {node_id} -->|"{edge_label}"| {next_id}')

    lines.append("```")
    return "\n".join(lines)


def _extract_edge_label(action: str) -> str:
    """Extract a short verb phrase for the Mermaid edge label."""
    action = action.strip()
    if not action:
        return "下一步"

    # Look for common action verbs and extract context
    verbs = ["点击", "选择", "输入", "填写", "上传", "提交", "确认", "切换", "搜索", "删除"]
    for verb in verbs:
        if verb in action:
            # Find the verb position and take verb + next few chars
            idx = action.find(verb)
            snippet = action[idx:idx + 8].rstrip("，。、")
            return snippet

    # Fallback: take first 6 chars
    return action[:6] + ("…" if len(action) > 6 else "")
