"""Stage 1: Video decoding and frame extraction using FFmpeg."""

import subprocess
import json
import os
import shutil
from pathlib import Path


def extract_frames(video_path: str, output_dir: str, fps: float = 2.0) -> dict:
    """
    Extract frames from video at specified FPS.
    Returns metadata dict with frame paths, duration, resolution.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video metadata
    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(video_path)
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if probe_result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {probe_result.stderr}")

    probe_data = json.loads(probe_result.stdout)

    # Extract video stream info
    video_stream = next(
        (s for s in probe_data["streams"] if s["codec_type"] == "video"),
        None
    )
    if not video_stream:
        raise RuntimeError("No video stream found in file")

    width = int(video_stream["width"])
    height = int(video_stream["height"])
    duration = float(probe_data["format"].get("duration", 0))

    # Warn if resolution is too low
    if width < 1280:
        print(f"⚠️  Video resolution {width}x{height} is below 1280px. Annotation quality may be reduced.")

    # Extract frames at target FPS
    frames_pattern = str(output_dir / "frame_%04d.png")

    # Scale down if wider than 1920px to manage file sizes
    scale_filter = f"fps={fps}"
    if width > 1920:
        scale_filter += f",scale=1920:-1"

    extract_cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", scale_filter,
        "-q:v", "2",  # high quality PNG
        frames_pattern,
        "-y"
    ]
    result = subprocess.run(extract_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed: {result.stderr}")

    # Collect extracted frames
    frame_files = sorted(output_dir.glob("frame_*.png"))

    metadata = {
        "video_path": str(video_path),
        "width": width,
        "height": height,
        "duration": duration,
        "fps_extracted": fps,
        "total_frames": len(frame_files),
        "frame_files": [str(f) for f in frame_files],
        "frames_dir": str(output_dir),
    }

    print(f"✅ Extracted {len(frame_files)} frames from {duration:.1f}s video ({width}x{height})")
    return metadata
