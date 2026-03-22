# Video2Manual

将操作录屏自动转换为带标注截图的 Markdown 操作手册。

**对比手工制作（30 分钟）→ 自动生成（2 分钟以内）**

## 快速开始

### 1. 安装依赖

```bash
# 安装 FFmpeg（macOS）
brew install ffmpeg

# 安装 Python 依赖
pip install -r requirements.txt
```

### 2. 设置 API Key

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

从 [console.anthropic.com](https://console.anthropic.com) 获取 API Key。

### 3. 使用方式

**方式一：Web UI（推荐，适合演示）**
```bash
streamlit run app.py
```
浏览器打开 http://localhost:8501，拖入视频即可。

**方式二：命令行**
```bash
python main.py 录屏.mp4 --context "广告投放平台" --output ./output
```

## 输出结构

```
output/manual/
├── 如何新建广告素材.md       # Markdown 操作手册
└── images/
    ├── step_01_annotated.png  # 标注截图（带红框、步骤序号）
    ├── step_02_annotated.png
    ├── ...
    └── flow_overview.png      # 操作流程总览图（所有步骤横向排列+箭头）
```

## 处理流水线

```
录屏视频
  → Stage 1: FFmpeg 按 2fps 抽帧
  → Stage 2: OpenCV 场景变化检测，定位 3-15 个候选关键帧
  → Stage 3: Claude Vision 一次分析所有关键帧
             - 筛选真正的操作步骤帧
             - 识别操作内容和 UI 元素位置
             - 生成专业中文步骤描述
  → Stage 4: Pillow 绘制标注（红色框选 + 步骤序号角标 + 文字标签）
  → Stage 5: 组装 Markdown（步骤 + 截图 + Mermaid 流程图 + 总览大图）
```

## 标注样式

| 样式 | 颜色 | 用途 |
|------|------|------|
| primary_action | 红色实线框 | 用户要点击的主要按钮 |
| reference | 蓝色虚线框 | 需要关注的参考区域 |
| input_field | 绿色框 | 需要填写的输入框 |
| warning | 橙色框 | 容易误操作的区域 |

## 注意事项

- 建议录制分辨率 1280x720 及以上
- 视频时长建议 10 秒到 5 分钟
- 单次 API 调用费用约 ¥0.5-2 元（取决于截图数量）
