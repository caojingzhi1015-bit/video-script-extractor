# video-script-extractor

从视频链接或本地文件自动提取脚本文稿的完整 pipeline。支持 **Whisper 语音转写** 与 **OCR 硬字幕提取** 双路并行，按时间轴匹配合并，输出双语对照字幕与结构化 Markdown 报告。

典型用途：把韩综/日综（带中文硬字幕）、B站视频、YouTube、抖音、播客等内容转成可编辑的脚本文稿。

## 能力

- 视频下载（yt-dlp，支持 1000+ 站点）
- 音频提取（ffmpeg → 16kHz 单声道 WAV）
- 语音转写（faster-whisper，100+ 语种自动检测）
- 硬字幕 OCR（RapidOCR，识别烧录在画面上的翻译字幕）
- 双语对照合并（按时间轴匹配，输出 SRT / 对照文本 / Markdown 报告）
- 结构化拆解（场景切分、金句提取、内容分析）

## 目录结构

```
video-script-extractor/
├── SKILL.md                      # Skill 主文档（触发条件 + 完整工作流）
├── references/
│   └── pipeline-guide.md         # Pipeline 架构、LLM 拆解 prompt 模板
└── scripts/
    ├── extract_audio.py          # 音频提取 → audio.wav
    ├── transcribe.py             # Whisper 语音转写 → transcript.json/srt/txt
    ├── ocr_subtitles.py          # OCR 硬字幕提取 → subtitles_ocr.json/srt/txt
    ├── merge_output.py           # 双语合并 → 5 个输出文件
    └── monitor.py                # 等待 pipeline 完成
```

## 安装

### 作为 AI Agent Skill 使用

复制到你的宿主 skills 目录即可：

```bash
# Claude Code
cp -r video-script-extractor ~/.claude/skills/

# Codex
cp -r video-script-extractor ~/.codex/skills/

# WorkBuddy / 其他兼容宿主
cp -r video-script-extractor ~/.workbuddy/skills/
```

### 作为独立脚本使用

需要 Python 3.9+：

```bash
pip install faster-whisper imageio-ffmpeg rapidocr-onnxruntime opencv-python yt-dlp
```

## 快速开始

```bash
# 1. 下载视频
yt-dlp -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best" \
  --merge-output-format mp4 --no-playlist "VIDEO_URL"

# 2. 提取音频
python scripts/extract_audio.py input.m4a audio.wav

# 3a. Whisper 转写
python scripts/transcribe.py audio.wav temp/

# 3b. OCR 硬字幕
python scripts/ocr_subtitles.py video.mp4 temp/ 1.0

# 4. 合并输出
python scripts/merge_output.py .
```

## 关键实践建议

⚠️ **两条 pipeline 不要并行跑。** Whisper 与 OCR 都会吃满 CPU，并行会互相抢资源导致两者都极慢（实测 31 分钟视频并行 4 小时仅完成 30%）。改为串行执行。

⚠️ **OCR 大文件视频先用 ffmpeg 抽帧。** 直接用 OpenCV 逐帧读 290MB 视频极慢；先 `ffmpeg -vf "fps=1,scale=640:-1"` 抽成图片再 OCR，快一个数量级。

⚠️ **长视频加 `PYTHONUNBUFFERED=1`。** 否则 stdout 被缓冲，看不到任何进度输出，难以判断是否卡死。

⚠️ **韩综/日综中字场景**：OCR 得到的中文硬字幕是专业翻译，本身已足够产出完整脚本；Whisper 原文只是可选补充，可后台跑而不阻塞交付。

## 环境要求

| 依赖 | 用途 |
|------|------|
| `yt-dlp` | 视频下载 |
| `imageio-ffmpeg` | 提供 ffmpeg 二进制（无需系统安装 ffmpeg） |
| `faster-whisper` | 语音转写（CTranslate2 加速） |
| `rapidocr-onnxruntime` | OCR 文字识别（轻量，无需 GPU） |
| `opencv-python` | 视频帧处理 |

无 CUDA 环境下必须强制 `device="cpu", compute_type="int8"`，否则 `device="auto"` 尝试 GPU 会报错。

## License

MIT
