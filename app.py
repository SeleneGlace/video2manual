"""
Video2Manual — Streamlit web UI for demo and daily use.

Run: streamlit run app.py
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="Video2Manual",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    font-size: 2.2rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.2rem;
}
.sub-header {
    font-size: 1rem;
    color: #64748b;
    margin-bottom: 2rem;
}
.step-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.5rem;
}
.metric-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)


def render_header():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<div class="main-header">📋 Video2Manual</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sub-header">上传操作录屏，自动生成带标注截图的 Markdown 操作手册</div>',
            unsafe_allow_html=True
        )
    with col2:
        st.markdown("")
        time_saved = st.empty()
        time_saved.markdown("""
        <div class="metric-box">
            <div style="font-size:1.8rem;font-weight:700;color:#3b82f6">~28 分钟</div>
            <div style="font-size:0.8rem;color:#64748b">每次节省的时间</div>
        </div>
        """, unsafe_allow_html=True)


def render_pipeline_status(current_stage=None, done=False):
    stages = [
        ("1", "视频解析", "抽帧"),
        ("2", "场景检测", "找关键帧"),
        ("3", "AI 分析", "理解操作"),
        ("4", "图片标注", "框选高亮"),
        ("5", "文档组装", "生成 Markdown"),
    ]
    cols = st.columns(len(stages))
    for col, (num, name, desc) in zip(cols, stages):
        with col:
            if done:
                icon = "✅"
                color = "#16a34a"
            elif current_stage and current_stage == f"Stage {num}/5":
                icon = "⚙️"
                color = "#3b82f6"
            elif current_stage and int(num) < int(current_stage.split("/")[0].replace("Stage ", "")):
                icon = "✅"
                color = "#16a34a"
            else:
                icon = f"**{num}**"
                color = "#94a3b8"
            st.markdown(
                f"<div style='text-align:center;color:{color}'>{icon}<br>"
                f"<b>{name}</b><br><small>{desc}</small></div>",
                unsafe_allow_html=True
            )


def main():
    render_header()

    st.divider()

    # Input section
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("① 上传录屏视频")
        video_file = st.file_uploader(
            "支持格式：MP4、MOV、WebM",
            type=["mp4", "mov", "webm"],
            help="建议录制分辨率 1280x720 及以上，时长 10 秒到 5 分钟"
        )

        platform_context = st.text_input(
            "平台名称（帮助 AI 理解上下文）",
            value="广告投放平台",
            help="输入你们平台的名称，AI 会生成更贴合业务的步骤描述"
        )

        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=os.environ.get("ANTHROPIC_API_KEY", ""),
            help="从 console.anthropic.com 获取"
        )

    with col_right:
        st.subheader("② 处理流程")
        pipeline_placeholder = st.empty()
        with pipeline_placeholder.container():
            render_pipeline_status()

    st.divider()

    # Generate button
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        generate_btn = st.button(
            "🚀 生成操作手册",
            type="primary",
            disabled=(not video_file or not api_key),
            use_container_width=True,
        )
    with col_info:
        if not video_file:
            st.info("请先上传视频文件")
        elif not api_key:
            st.warning("请输入 Anthropic API Key")
        else:
            st.success("准备就绪，点击生成按钮开始处理")

    # Results section
    if generate_btn:
        if not video_file or not api_key:
            st.error("请填写所有必填项")
            return

        os.environ["ANTHROPIC_API_KEY"] = api_key

        # Save uploaded file to temp dir
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, video_file.name)
            with open(video_path, "wb") as f:
                f.write(video_file.getbuffer())

            output_dir = os.path.join(tmp_dir, "output")

            # Progress tracking
            progress_log = []
            log_placeholder = st.empty()
            status_text = st.empty()

            def on_progress(stage, msg):
                progress_log.append(f"**{stage}** — {msg}")
                with pipeline_placeholder.container():
                    render_pipeline_status(current_stage=stage)
                log_placeholder.markdown("\n\n".join(progress_log[-5:]))
                status_text.info(msg)

            try:
                # Add project root to path
                sys.path.insert(0, str(Path(__file__).parent))
                from main import run_pipeline

                with st.spinner("正在处理，请稍候..."):
                    md_path = run_pipeline(
                        video_path=video_path,
                        output_dir=output_dir,
                        platform_context=platform_context,
                        on_progress=on_progress,
                    )

                # Success!
                with pipeline_placeholder.container():
                    render_pipeline_status(done=True)
                status_text.success("🎉 操作手册生成成功！")
                log_placeholder.empty()

                st.divider()
                st.subheader("③ 生成结果")

                # Read the output
                md_content = Path(md_path).read_text(encoding="utf-8")
                manual_dir = Path(md_path).parent

                # Preview tabs
                tab_preview, tab_raw, tab_images = st.tabs([
                    "📖 预览", "📝 Markdown 源码", "🖼️ 标注截图"
                ])

                with tab_preview:
                    st.markdown(md_content)

                with tab_raw:
                    st.code(md_content, language="markdown")
                    st.download_button(
                        "⬇️ 下载 Markdown 文件",
                        data=md_content.encode("utf-8"),
                        file_name=Path(md_path).name,
                        mime="text/markdown",
                    )

                with tab_images:
                    images_dir = manual_dir / "images"
                    if images_dir.exists():
                        img_files = sorted(images_dir.glob("step_*.png"))
                        overview = images_dir / "flow_overview.png"

                        if overview.exists():
                            st.image(str(overview), caption="操作流程总览", use_column_width=True)
                            st.divider()

                        for img_file in img_files:
                            step_num = img_file.stem.split("_")[1]
                            st.image(str(img_file), caption=f"步骤 {int(step_num)} 标注截图",
                                    use_column_width=True)

                # Download as zip
                zip_path = shutil.make_archive(
                    str(manual_dir.parent / "manual"), "zip", str(manual_dir)
                )
                with open(zip_path, "rb") as f:
                    st.download_button(
                        "📦 下载完整手册（Markdown + 图片）",
                        data=f.read(),
                        file_name="manual.zip",
                        mime="application/zip",
                        type="primary",
                    )

            except Exception as e:
                st.error(f"❌ 处理失败：{str(e)}")
                with st.expander("错误详情"):
                    import traceback
                    st.code(traceback.format_exc())

    # Footer
    st.divider()
    st.caption(
        "Video2Manual · 基于 Claude Vision API · "
        "对比手工制作（30 分钟）可节省约 93% 的时间"
    )


if __name__ == "__main__":
    main()
