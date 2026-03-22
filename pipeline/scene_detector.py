"""Stage 2: Scene change detection to find candidate keyframes."""

import cv2
import numpy as np
from pathlib import Path


def compute_frame_diff(frame1_path: str, frame2_path: str) -> float:
    """
    Compute structural similarity difference between two frames.
    Returns a value 0-1 where higher means more different.
    """
    img1 = cv2.imread(frame1_path, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(frame2_path, cv2.IMREAD_GRAYSCALE)

    if img1 is None or img2 is None:
        return 0.0

    # Resize to smaller size for faster comparison
    h, w = 270, 480
    img1 = cv2.resize(img1, (w, h))
    img2 = cv2.resize(img2, (w, h))

    # Compute absolute difference
    diff = cv2.absdiff(img1, img2)
    diff_score = diff.mean() / 255.0
    return diff_score


def detect_scene_changes(frame_files: list, threshold: float = 0.05) -> list:
    """
    Detect scene changes in the frame sequence.
    Returns list of candidate keyframe indices (0-based).

    threshold: fraction of pixels that must change to count as a scene change.
    Lower = more sensitive. 0.05 means 5% pixel change.
    """
    if not frame_files:
        return []

    # Always include the first frame
    candidates = [0]

    print(f"🔍 Analyzing {len(frame_files)} frames for scene changes...")

    for i in range(1, len(frame_files)):
        diff = compute_frame_diff(frame_files[i - 1], frame_files[i])
        if diff > threshold:
            # Wait for stability — take the frame 1 second after the change
            # (at 2fps that means the next frame)
            stable_idx = min(i + 1, len(frame_files) - 1)
            if stable_idx not in candidates:
                candidates.append(stable_idx)

    # Also always consider the last frame
    last = len(frame_files) - 1
    if last not in candidates:
        candidates.append(last)

    # Deduplicate and sort
    candidates = sorted(set(candidates))

    # If we have too many candidates (>15), the video may have lots of animation.
    # Take every other one to reduce to a manageable set.
    if len(candidates) > 15:
        print(f"⚠️  {len(candidates)} scene changes detected, sampling down to top 15")
        # Keep first, last, and evenly spaced in between
        step = len(candidates) // 14
        reduced = [candidates[0]] + candidates[1:-1:step] + [candidates[-1]]
        candidates = reduced[:15]

    print(f"✅ Found {len(candidates)} candidate keyframes: indices {candidates}")
    return candidates


def extract_candidate_frames(frame_files: list, candidate_indices: list) -> list:
    """Return the file paths for the candidate keyframe indices."""
    return [frame_files[i] for i in candidate_indices if i < len(frame_files)]
