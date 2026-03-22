"""
Video2Manual — Main pipeline orchestrator.

Usage:
  python main.py <video_path> [--context "平台名称"] [--output ./output]
"""

import argparse
import os
import sys
import tempfile
import shutil
from pathlib import Path

from pipeline.video_processor import extract_frames
from pipeline.scene_detector import detect_scene_changes, extract_candidate_frames
from pipeline.llm_analyzer import analyze_frames
from pipeline.image_annotator import annotate_frame, create_flow_overview
from pipeline.doc_assembler import assemble_markdown


def run_pipeline(
    video_path: str,
    output_dir: str,
    platform_context: str = "广告投放平台",
    on_progress=None,
) -> str:
    """
    Run the full Video2Manual pipeline.

    Args:
        video_path: Path to the screen recording video
        output_dir: Directory to write the output manual
        platform_context: Platform name for LLM context
        on_progress: Optional callback(stage, message) for progress updates

    Returns:
        Path to the generated Markdown file
    """
    def progress(stage, msg):
        print(f"[{stage}] {msg}")
        if on_progress:
            on_progress(stage, msg)

    # Working directory for intermediate files
    work_dir = Path(output_dir) / "_work"
    frames_dir = work_dir / "frames"
    annotated_dir = work_dir / "annotated"

    try:
        # --- Stage 1: Extract frames ---
        progress("Stage 1/5", "解析视频并提取帧...")
        metadata = extract_frames(str(video_path), str(frames_dir), fps=2.0)
        frame_files = metadata["frame_files"]

        if not frame_files:
            raise RuntimeError("未能从视频中提取到帧，请检查视频文件格式")

        # --- Stage 2: Scene detection ---
        progress("Stage 2/5", "检测场景变化，定位关键操作帧...")
        candidate_indices = detect_scene_changes(frame_files, threshold=0.05)
        candidate_frames = extract_candidate_frames(frame_files, candidate_indices)

        if not candidate_frames:
            raise RuntimeError("未检测到场景变化，视频可能是静态画面")

        # Cap at 12 frames to manage LLM cost
        if len(candidate_frames) > 12:
            progress("Stage 2/5", f"候选帧过多 ({len(candidate_frames)})，保留最具代表性的 12 帧")
            step = len(candidate_frames) // 11
            candidate_frames = ([candidate_frames[0]]
                               + candidate_frames[1:-1:step]
                               + [candidate_frames[-1]])[:12]

        # --- Stage 3: LLM analysis ---
        progress("Stage 3/5", f"AI 分析 {len(candidate_frames)} 张候选帧（这一步需要约 20-40 秒）...")
        step_data = analyze_frames(candidate_frames, platform_context)

        steps = step_data.get("steps", [])
        if not steps:
            raise RuntimeError("AI 未能识别出有效的操作步骤，请检查视频内容")

        # --- Stage 4: Annotate images ---
        progress("Stage 4/5", f"为 {len(steps)} 个步骤添加标注...")
        annotated_paths = []
        for i, step in enumerate(steps):
            frame_idx = step.get("frame_index", 0)
            frame_path = (candidate_frames[frame_idx]
                         if frame_idx < len(candidate_frames)
                         else candidate_frames[0])

            out_path = str(annotated_dir / f"step_{i + 1:02d}.png")
            annotated = annotate_frame(
                frame_path=frame_path,
                highlight_regions=step.get("highlight_regions", []),
                step_number=step.get("step_number", i + 1),
                output_path=out_path,
            )
            annotated_paths.append(annotated)
            progress("Stage 4/5", f"  ✓ 步骤 {i + 1}/{len(steps)} 标注完成")

        # Create flow overview image
        step_titles = [s.get("page_name", "") for s in steps]
        flow_path = str(annotated_dir / "flow_overview.png")
        create_flow_overview(annotated_paths, step_titles, flow_path)

        # --- Stage 5: Assemble document ---
        progress("Stage 5/5", "组装 Markdown 操作手册...")
        final_output_dir = Path(output_dir) / "manual"
        md_path = assemble_markdown(
            step_data=step_data,
            annotated_image_paths=annotated_paths,
            flow_overview_path=flow_path,
            output_dir=str(final_output_dir),
            platform_context=platform_context,
        )

        progress("完成", f"🎉 操作手册已生成：{md_path}")
        return md_path

    finally:
        # Clean up intermediate work directory
        if work_dir.exists():
            shutil.rmtree(str(work_dir), ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Video2Manual: 将操作录屏转换为 Markdown 操作手册"
    )
    parser.add_argument("video", help="录屏视频文件路径 (.mp4 / .mov)")
    parser.add_argument(
        "--context",
        default="广告投放平台",
        help="平台名称，用于 AI 理解上下文（默认：广告投放平台）"
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="输出目录（默认：./output）"
    )

    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"❌ 错误：视频文件不存在：{args.video}")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 错误：请设置 ANTHROPIC_API_KEY 环境变量")
        print("   export ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)

    try:
        md_path = run_pipeline(
            video_path=args.video,
            output_dir=args.output,
            platform_context=args.context,
        )
        print(f"\n✅ 完成！输出文件：{md_path}")
    except Exception as e:
        print(f"\n❌ 失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
