"""
Step 3: 语音转写
用 faster-whisper 把音频转成带时间戳的逐字文稿
"""
import json
import sys
import os

# ffmpeg 二进制路径（imageio-ffmpeg 提供）
import imageio_ffmpeg
os.environ["FFMPEG_BINARY"] = imageio_ffmpeg.get_ffmpeg_exe()

from faster_whisper import WhisperModel


def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{m:02d}:{s:02d},{ms:03d}"


def transcribe(audio_path, output_dir, language=None):
    print(f"[transcribe] loading model 'medium' (device=cpu, int8)...")
    # 强制 CPU 模式（无 CUDA 环境），int8 量化在 CPU 上最快
    model = WhisperModel("medium", device="cpu", compute_type="int8")

    print(f"[transcribe] transcribing {audio_path} ...")
    segments, info = model.transcribe(
        audio_path,
        language=language,        # None=自动检测
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200
        ),
        word_timestamps=False
    )

    print(f"[transcribe] detected language: {info.language} (prob={info.language_probability:.2f})")

    results = []
    for seg in segments:
        results.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip()
        })

    # 保存 JSON
    json_path = os.path.join(output_dir, "transcript.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"language": info.language, "segments": results}, f, ensure_ascii=False, indent=2)

    # 保存 SRT 字幕格式
    srt_path = os.path.join(output_dir, "transcript.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(results, 1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

    # 保存纯文本（带时间戳）
    txt_path = os.path.join(output_dir, "transcript.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in results:
            f.write(f"[{format_timestamp(seg['start'])}] {seg['text']}\n")

    print(f"[transcribe] done. {len(results)} segments.")
    print(f"  JSON: {json_path}")
    print(f"  SRT:  {srt_path}")
    print(f"  TXT:  {txt_path}")
    return json_path


if __name__ == "__main__":
    audio_path = sys.argv[1]
    output_dir = sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else None
    transcribe(audio_path, output_dir, lang)
