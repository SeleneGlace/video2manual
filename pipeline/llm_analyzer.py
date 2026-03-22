"""Stage 3: LLM-based semantic understanding of keyframes."""

import base64
import json
import os
from pathlib import Path


def encode_image(image_path: str) -> str:
    """Encode image to base64 for API transmission."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_frames(frame_paths: list, platform_context: str = "广告投放平台") -> dict:
    """
    Send candidate keyframes to Claude Vision API for semantic analysis.
    Returns structured step data.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Get your API key from https://console.anthropic.com/"
        )

    # Load the prompt template
    prompt_file = Path(__file__).parent.parent / "prompts" / "step_analysis.txt"
    system_prompt = prompt_file.read_text(encoding="utf-8")

    client = anthropic.Anthropic(api_key=api_key)

    # Build the message content — all frames in one request for context coherence
    content = []

    content.append({
        "type": "text",
        "text": f"以下是从【{platform_context}】操作录屏中提取的 {len(frame_paths)} 张候选截图，按时间顺序排列（帧编号从 0 开始）。请按照系统提示中的要求分析这些截图并输出 JSON。"
    })

    for idx, frame_path in enumerate(frame_paths):
        content.append({
            "type": "text",
            "text": f"--- 帧 {idx} ---"
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": encode_image(frame_path)
            }
        })

    print(f"🤖 Sending {len(frame_paths)} frames to Claude Vision API...")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": content}]
    )

    raw_response = response.content[0].text

    # Parse JSON from response
    # Claude sometimes wraps JSON in markdown code blocks
    raw_response = raw_response.strip()
    if raw_response.startswith("```"):
        lines = raw_response.split("\n")
        # Remove first and last ``` lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_response = "\n".join(lines)

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse LLM response as JSON: {e}\nRaw response:\n{raw_response[:500]}")

    # Validate and fix common issues
    result = _validate_and_fix(result, len(frame_paths))

    print(f"✅ LLM analysis complete: {len(result['steps'])} steps identified")
    print(f"   Title: {result['title']}")
    return result


def _validate_and_fix(result: dict, num_frames: int) -> dict:
    """Validate LLM output and fix common issues."""

    # Ensure required fields exist
    if "title" not in result:
        result["title"] = "操作手册"
    if "summary" not in result:
        result["summary"] = ""
    if "steps" not in result:
        result["steps"] = []

    # Fix bbox values — ensure they're within [0, 100] and reasonable sizes
    for step in result.get("steps", []):
        for region in step.get("highlight_regions", []):
            bbox = region.get("bbox_pct", [])
            if len(bbox) == 4:
                x, y, w, h = bbox
                # Clamp to valid range
                x = max(0, min(95, float(x)))
                y = max(0, min(95, float(y)))
                w = max(3, min(100 - x, float(w)))  # minimum 3% width
                h = max(2, min(100 - y, float(h)))  # minimum 2% height
                region["bbox_pct"] = [x, y, w, h]
            else:
                # Invalid bbox — remove the region
                region["bbox_pct"] = []

        # Remove regions with invalid bbox
        step["highlight_regions"] = [
            r for r in step.get("highlight_regions", [])
            if len(r.get("bbox_pct", [])) == 4
        ]

        # Ensure frame_index is within bounds
        if "frame_index" not in step or step["frame_index"] >= num_frames:
            step["frame_index"] = 0

        # Ensure style is valid
        valid_styles = {"primary_action", "reference", "input_field", "warning"}
        for region in step.get("highlight_regions", []):
            if region.get("style") not in valid_styles:
                region["style"] = "primary_action"

    return result
