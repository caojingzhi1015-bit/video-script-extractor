"""
Step 5: 合并输出 — 中韩双字幕
把 Whisper 韩语转写 + OCR 中文字幕 整合成：
1. 双语 SRT（中韩对照，按 OCR 字幕时间轴）
2. 双语对照纯文本
3. 结构化 Markdown（完整拆解）
"""
import os
import sys
import json
from datetime import datetime


def format_ts(sec):
    h = int(sec // 3600)
    m = int(sec % 3600) // 60
    s = int(sec % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_srt_ts(sec):
    h = int(sec // 3600)
    m = int(sec % 3600) // 60
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def match_by_time(ocr_subs, whisper_segs):
    """
    对每条 OCR 中文字幕，找到时间上重叠的 Whisper 韩文文本。
    返回 [{start, end, zh, ko}]
    """
    results = []
    for sub in ocr_subs:
        s, e = sub["start"], sub["end"]
        zh = sub["text"]

        # 找到与这条字幕时间重叠的所有 whisper 段
        ko_parts = []
        for seg in whisper_segs:
            ws, we = seg["start"], seg["end"]
            # 有重叠
            if ws < e and we > s:
                ko_parts.append(seg["text"].strip())

        ko = " ".join(ko_parts) if ko_parts else ""
        results.append({
            "start": s,
            "end": e,
            "zh": zh,
            "ko": ko
        })
    return results


def write_bilingual_srt(matched, path):
    """双语 SRT：每条字幕上面中文，下面韩文"""
    with open(path, "w", encoding="utf-8") as f:
        for i, m in enumerate(matched, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_ts(m['start'])} --> {format_srt_ts(m['end'])}\n")
            f.write(f"{m['zh']}\n")
            if m["ko"]:
                f.write(f"{m['ko']}\n")
            f.write("\n")
    print(f"  双语 SRT: {path}")


def write_bilingual_txt(matched, path):
    """双语对照纯文本"""
    with open(path, "w", encoding="utf-8") as f:
        for m in matched:
            ts = format_ts(m["start"])
            f.write(f"[{ts}] 中: {m['zh']}\n")
            if m["ko"]:
                f.write(f"         韩: {m['ko']}\n")
            else:
                f.write(f"         韩: (无匹配)\n")
            f.write("\n")
    print(f"  双语对照: {path}")


def write_korean_srt(whisper_data, path):
    """纯韩文 SRT"""
    segs = whisper_data.get("segments", [])
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segs, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_ts(seg['start'])} --> {format_srt_ts(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
    print(f"  韩文 SRT: {path}")


def write_chinese_srt(ocr_subs, path):
    """纯中文 SRT"""
    with open(path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(ocr_subs, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_ts(sub['start'])} --> {format_srt_ts(sub['end'])}\n")
            f.write(f"{sub['text']}\n\n")
    print(f"  中文 SRT: {path}")


def write_markdown(metadata, transcript_data, subtitle_data, matched, output_path):
    """结构化 Markdown 完整报告"""
    lines = []

    # 头部
    lines.append(f"# {metadata.get('title', '视频脚本拆解')}\n")
    lines.append(f"> **UP主**：{metadata.get('uploader', '')}  ")
    lines.append(f"> **平台**：哔哩哔哩 (Bilibili)  ")
    lines.append(f"> **时长**：{format_ts(metadata.get('duration', 0))}  ")
    lines.append(f"> **链接**：{metadata.get('url', '')}  ")
    lines.append(f"> **提取时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")

    # 提取说明
    lines.append("## 📋 提取说明\n")
    lines.append("本文档包含 **中韩双字幕**，由两条 pipeline 并行提取：")
    lines.append("- **中文字幕**：OCR 从画面硬字幕提取（专业人工翻译，精效中字）")
    if transcript_data:
        lang = transcript_data.get("language", "未知")
        segs = transcript_data.get("segments", [])
        lines.append(f"- **韩文转写**：faster-whisper 转写音轨，检测语言：**{lang}**，共 **{len(segs)}** 段")
    lines.append(f"- **中韩对照**：按时间轴匹配，共 **{len(matched)}** 条双语字幕\n")
    lines.append("---\n")

    # 中韩双语对照
    if matched:
        lines.append("## 🔄 中韩双语对照\n")
        lines.append("| 时间 | 中文字幕 | 韩文原声 |")
        lines.append("|------|---------|---------|")
        for m in matched:
            ts = format_ts(m["start"])
            zh = m["zh"].replace("|", "\\|")
            ko = m["ko"].replace("|", "\\|") if m["ko"] else "—"
            lines.append(f"| {ts} | {zh} | {ko} |")
        lines.append("\n---\n")

    # 中文硬字幕全文
    if subtitle_data:
        lines.append("## 📝 中文硬字幕全文\n")
        lines.append(f"共 **{len(subtitle_data)}** 段。\n")
        for sub in subtitle_data:
            lines.append(f"**[{format_ts(sub['start'])}-{format_ts(sub['end'])}]** {sub['text']}\n")
        lines.append("---\n")

    # 韩文转写全文
    if transcript_data:
        segs = transcript_data.get("segments", [])
        lines.append("## 🎙️ 韩文原声转写全文（Whisper）\n")
        lines.append(f"检测语言：**{transcript_data.get('language', '?')}** | 共 **{len(segs)}** 段。\n")
        for seg in segs:
            lines.append(f"**[{format_ts(seg['start'])}]** {seg['text']}\n")
        lines.append("---\n")

    # 中文纯文本（方便复制）
    if subtitle_data:
        lines.append("## 📄 中文字幕纯文本\n")
        full_text = " ".join([seg["text"] for seg in subtitle_data])
        lines.append(full_text + "\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Markdown: {output_path}")


if __name__ == "__main__":
    work_dir = sys.argv[1]
    temp_dir = os.path.join(work_dir, "temp")
    output_dir = os.path.join(work_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    metadata = {
        "title": "【三站联合】『251114』[又BOYZ] EP.09 拜托就老实呆着吧!!!我做啥了啊?! | 飞椅 #1 | 精效中字",
        "uploader": "李贤在HJ_Presentizm / 三站联合制作",
        "duration": 1885,
        "url": "https://www.bilibili.com/video/BV1bFCUBfEUs/"
    }

    transcript = load_json(os.path.join(temp_dir, "transcript.json"))
    subtitles = load_json(os.path.join(temp_dir, "subtitles_ocr.json"))

    # 标准化 subtitles 格式
    if isinstance(subtitles, dict) and "segments" in subtitles:
        subtitles = subtitles["segments"]
    if subtitles is None:
        subtitles = []

    whisper_segs = transcript.get("segments", []) if transcript else []

    if not transcript and not subtitles:
        print("[merge] ERROR: 没有找到任何提取结果")
        sys.exit(1)

    print(f"[merge] whisper: {len(whisper_segs)} segments, ocr: {len(subtitles)} subtitles")

    # 时间轴匹配
    matched = match_by_time(subtitles, whisper_segs) if subtitles and whisper_segs else []

    # 输出文件
    base = "boyz_ep09"

    if matched:
        write_bilingual_srt(matched, os.path.join(output_dir, f"{base}_中韩双语.srt"))
        write_bilingual_txt(matched, os.path.join(output_dir, f"{base}_中韩对照.txt"))

    if transcript:
        write_korean_srt(transcript, os.path.join(output_dir, f"{base}_韩文.srt"))

    if subtitles:
        write_chinese_srt(subtitles, os.path.join(output_dir, f"{base}_中文.srt"))

    write_markdown(metadata, transcript, subtitles, matched,
                   os.path.join(output_dir, f"{base}_脚本提取.md"))

    print(f"\n[merge] 全部完成！输出目录: {output_dir}")
