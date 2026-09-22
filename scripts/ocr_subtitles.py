"""
Step 4 (OCR): 提取视频画面中的硬字幕（中文）
策略：
  1. 按 1fps 抽帧
  2. 裁剪画面底部 30%（字幕通常所在区域）
  3. 用图像哈希检测字幕区域是否变化
  4. 仅对变化的帧做 OCR
  5. 去重合并，输出带时间戳的字幕文本
"""
import os
import sys
import json
import time
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR


def phash(img, hash_size=16):
    """感知哈希，用于快速判断两帧字幕区是否相似"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    resized = cv2.resize(gray, (hash_size, hash_size))
    avg = resized.mean()
    return (resized > avg).flatten()


def hamming(h1, h2):
    return np.count_nonzero(h1 != h2)


def format_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def extract_subtitles(video_path, output_dir, fps=1.0, crop_ratio=0.32, diff_threshold=8):
    """
    video_path: 视频文件
    fps: 抽帧率（每秒几帧）
    crop_ratio: 从底部裁剪多大比例作为字幕区
    diff_threshold: 哈明距离小于此值认为字幕没变，跳过OCR
    """
    print(f"[ocr] loading RapidOCR...")
    ocr = RapidOCR()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / video_fps if video_fps > 0 else 0
    print(f"[ocr] video: {total_frames} frames, {video_fps:.1f} fps, {duration:.0f}s ({format_ts(duration)})")

    frame_interval = max(1, int(video_fps / fps)) if video_fps > 0 else 1
    print(f"[ocr] sampling every {frame_interval} frames (~{fps} fps), crop bottom {int(crop_ratio*100)}%")

    results = []          # [{start, end, text}]
    prev_hash = None
    current_text = None
    current_start = None
    frame_idx = 0
    ocr_count = 0
    sample_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            sample_count += 1
            h, w = frame.shape[:2]
            # 裁剪底部字幕区
            crop = frame[int(h * (1 - crop_ratio)):, :]

            curr_hash = phash(crop)

            # 判断字幕区是否变化
            need_ocr = True
            if prev_hash is not None:
                dist = hamming(curr_hash, prev_hash)
                if dist < diff_threshold:
                    need_ocr = False

            if need_ocr:
                ocr_count += 1
                try:
                    ocr_result, _ = ocr(crop)
                except Exception as e:
                    ocr_result = None

                # 提取文本（按 y 坐标排序，从上到下）
                lines = []
                if ocr_result:
                    for item in ocr_result:
                        # RapidOCR 返回格式: [box, text, confidence]
                        box, text, conf = item[0], item[1], item[2]
                        try:
                            conf = float(conf)
                        except (TypeError, ValueError):
                            conf = 0.0
                        if text.strip() and conf > 0.3:
                            # box 是 4 个点的坐标 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                            y_center = (box[0][1] + box[2][1]) / 2
                            lines.append((y_center, text.strip()))
                    lines.sort(key=lambda x: x[0])
                    text = " ".join([t for _, t in lines])
                else:
                    text = ""

                # 如果文本变化了，保存上一段，开始新一段
                if text != current_text:
                    if current_text and current_start is not None:
                        ts = frame_idx / video_fps if video_fps > 0 else 0
                        results.append({
                            "start": round(current_start, 2),
                            "end": round(ts, 2),
                            "text": current_text
                        })
                    current_text = text
                    current_start = frame_idx / video_fps if video_fps > 0 else 0

            prev_hash = curr_hash

        frame_idx += 1
        if frame_idx % 500 == 0:
            print(f"[ocr] progress: {frame_idx}/{total_frames} frames, {ocr_count} OCR calls, {len(results)} segments...")

    # 收尾
    if current_text and current_start is not None:
        results.append({
            "start": round(current_start, 2),
            "end": round(duration, 2),
            "text": current_text
        })

    cap.release()

    # 过滤空文本
    results = [r for r in results if r["text"].strip()]

    print(f"[ocr] done. sampled {sample_count} frames, {ocr_count} OCR calls, {len(results)} subtitle segments.")

    # 保存 JSON
    json_path = os.path.join(output_dir, "subtitles_ocr.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 保存 SRT
    def srt_ts(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_path = os.path.join(output_dir, "subtitles_ocr.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(results, 1):
            f.write(f"{i}\n")
            f.write(f"{srt_ts(seg['start'])} --> {srt_ts(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

    # 保存纯文本
    txt_path = os.path.join(output_dir, "subtitles_ocr.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in results:
            f.write(f"[{format_ts(seg['start'])}-{format_ts(seg['end'])}] {seg['text']}\n")

    print(f"  JSON: {json_path}")
    print(f"  SRT:  {srt_path}")
    print(f"  TXT:  {txt_path}")
    return json_path


if __name__ == "__main__":
    video_path = sys.argv[1]
    output_dir = sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    extract_subtitles(video_path, output_dir, fps=fps)
