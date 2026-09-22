"""
Step 2: 音频提取
用 ffmpeg 从视频提取 16kHz 单声道 WAV（Whisper 最优输入）
"""
import os
import sys
import subprocess
import imageio_ffmpeg


def extract_audio(video_path, output_wav):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vn",                    # 不要视频
        "-acodec", "pcm_s16le",   # 16-bit PCM
        "-ar", "16000",           # 16kHz 采样率
        "-ac", "1",               # 单声道
        "-y",                     # 覆盖输出
        output_wav
    ]
    print(f"[audio] extracting audio from {video_path} -> {output_wav}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[audio] ERROR: {result.stderr[-500:]}")
        raise RuntimeError("ffmpeg failed")
    print(f"[audio] done. size={os.path.getsize(output_wav)} bytes")
    return output_wav


if __name__ == "__main__":
    video_path = sys.argv[1]
    output_wav = sys.argv[2]
    extract_audio(video_path, output_wav)
