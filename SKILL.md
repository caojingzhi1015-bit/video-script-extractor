---
name: video-script-extractor
description: "视频脚本提取与结构化拆解。输入视频链接（YouTube/B站/抖音/TikTok/小红书等）或本地视频文件，自动完成下载、音频提取、语音转写（Whisper）、硬字幕OCR、结构化拆解，输出带时间戳的脚本文稿。支持中韩/中英等多语种双字幕对照提取。当用户提到提取视频脚本、视频转文字、提取字幕、视频拆解、下载视频并转写、video transcript、extract subtitles 时触发此 skill。"
agent_created: true
---

# Video Script Extractor

## Overview

从视频链接或本地文件自动提取脚本文稿的完整 pipeline。支持两条并行提取路径：
- **Whisper 语音转写**：从音轨转写原声文稿（支持 100+ 语种自动检测）
- **OCR 硬字幕提取**：从画面识别烧录字幕（适用于韩综/日综等带翻译字幕的视频）

两条路径按时间轴匹配合并，可输出双语对照 SRT、纯文本对照、结构化 Markdown 报告。

## 触发场景

- 用户发来视频链接（B站/YouTube/抖音等），要求提取脚本/字幕/文稿
- 用户提供本地视频文件，要求转写或拆解
- 用户要求提取视频中的"硬字幕"（烧录在画面上的字幕）
- 用户要求中韩/中英双语对照字幕
- 用户要求对视频内容做结构化拆解（场景切分、金句提取、内容分析）

## Pipeline 架构（5 步）

```
[输入: URL 或文件路径]
  │
  ├─ Step 1: 视频获取 ──── yt-dlp 下载 / 本地文件直用
  │
  ├─ Step 2: 音频提取 ──── ffmpeg → 16kHz 单声道 WAV
  │
  ├─ Step 3: 双路并行提取
  │    ├─ 3a: Whisper 转写 ── 音轨 → 带时间戳文稿（原声语言）
  │    └─ 3b: OCR 字幕提取 ── 画面帧 → 烧录字幕文本（翻译语言）
  │
  ├─ Step 4: 结构化拆解 ── LLM 智能分段 + 内容分析（可选）
  │
  └─ Step 5: 合并输出 ──── 双语 SRT + 对照文本 + Markdown 报告
```

## 环境准备

### Python 虚拟环境

使用 managed Python 创建隔离 venv，所有依赖装在 venv 内：

```bash
# 创建 venv（如果不存在）
"C:\Users\餐巾纸\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m venv "C:\Users\餐巾纸\.workbuddy\binaries\python\envs\default"

# 安装依赖
"C:\Users\餐巾纸\.workbuddy\binaries\python\envs\default\Scripts\python.exe" -m pip install faster-whisper imageio-ffmpeg rapidocr-onnxruntime opencv-python yt-dlp
```

### 关键依赖说明

| 依赖 | 用途 | 备注 |
|------|------|------|
| `yt-dlp` | 视频下载 | 支持 1000+ 站点 |
| `imageio-ffmpeg` | 提供 ffmpeg 二进制 | 无需系统安装 ffmpeg |
| `faster-whisper` | 语音转写 | CTranslate2 加速，比官方快 2-4x |
| `rapidocr-onnxruntime` | OCR 文字识别 | 轻量级，无需 GPU |
| `opencv-python` | 视频帧处理 | 抽帧、裁剪、哈希对比 |

### ffmpeg 二进制路径获取

不依赖系统 ffmpeg，用 imageio-ffmpeg 提供的二进制：

```python
import imageio_ffmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
```

## 工作流程

### Step 1: 视频获取

**URL 输入** → 用 yt-dlp 下载：

```bash
yt-dlp -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best" \
  --merge-output-format mp4 -o "%(title).80s.%(ext)s" --no-playlist "URL"
```

**本地文件** → 直接使用。

**B站特殊处理**：
- B站很多视频没有官方字幕 API（`subtitle.list` 为空）
- 硬字幕（烧录在画面上的中文翻译）只能通过 OCR 提取
- 下载时视频和音频是分开的两个文件（`.mp4` + `.m4a`），无需合并——OCR 用视频，Whisper 用音频

### Step 2: 音频提取

用 imageio-ffmpeg 提供的二进制提取 16kHz 单声道 WAV：

```bash
"<ffmpeg_path>" -i "input.m4a" -vn -acodec pcm_s16le -ar 16000 -ac 1 -y "audio.wav"
```

### Step 3a: Whisper 语音转写

运行 `scripts/transcribe.py`：

```bash
python scripts/transcribe.py <audio.wav> <output_dir> [language]
```

**关键参数**：
- 模型：`medium`（中文/韩文准确度好，速度适中）
- device：`cpu`（无 CUDA 环境时必须强制 CPU）
- compute_type：`int8`（CPU 上最快的量化模式）
- language：`None`（自动检测）或 `"zh"` / `"ko"` / `"en"` 等

**踩坑经验**：
- ⚠️ 无 CUDA 环境下 `device="auto"` 会尝试 GPU 然后报错，必须用 `device="cpu", compute_type="int8"`
- ⚠️ 31 分钟音频在 CPU 上跑 medium 模型约需 15-25 分钟（实测竞争资源时会拖到 40 分钟以上）
- ⚠️ 模型首次加载需下载 ~1.5GB，日志停在 `loading model` 属正常，别误判为卡死
- ⚠️ stdout 有缓冲，看不到进度；必须加 `PYTHONUNBUFFERED=1` 才能看到分段输出

### Step 3b: OCR 硬字幕提取

**推荐做法（快 10 倍以上）**：先用 ffmpeg 抽帧存成图片，再对图片做 OCR。
不要直接用 OpenCV 逐帧读视频——大文件（290MB）随机 seek 极慢，实测 4 小时只处理 30%。

```bash
# 1) ffmpeg 抽帧：1fps + 缩放到 640px 宽（OCR 足够，几秒完成）
<ffmpeg> -i video.mp4 -vf "fps=1,scale=640:-1" -q:v 2 -y frames/frame_%05d.jpg
```

```python
# 2) 对图片做 OCR：裁剪底部字幕区 + 帧间去重
import cv2, glob
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
for path in sorted(glob.glob("frames/*.jpg")):
    img = cv2.imread(path)
    h = img.shape[0]
    crop = img[int(h*0.68):, :]          # 底部 32% 是字幕区
    result, _ = ocr(crop)
    ...
```

直接跑内置脚本也可以（小文件适用）：

```bash
python scripts/ocr_subtitles.py <video.mp4> <output_dir> [fps=1.0]
```

**策略**：
- 按 1fps 抽帧（平衡速度与精度）
- 裁剪画面底部 32%（字幕通常所在区域）
- 用感知哈希（pHash）检测字幕区是否变化，跳过无变化帧
- 仅对变化帧做 OCR，去重合并

**踩坑经验**：
- ⚠️ RapidOCR 返回的 confidence 可能是字符串，需 `float()` 转换后再比较
- ⚠️ RapidOCR 返回格式为 `[box, text, confidence]` 三元组列表，不是 `(box, text, conf)`
- ⚠️ OCR 结果按 y 坐标排序拼接，保证多行字幕顺序正确

### Step 3 执行顺序：串行，不要并行

⚠️ **实测教训：两条 pipeline 不要同时跑。**

CPU 核心有限时，Whisper（~1.5GB 内存、吃满多核）与 OCR 并行会互相抢资源，
实测 31 分钟视频并行 4 小时只完成 30%，且两者都没产出。正确顺序：

```bash
# 1) 先单独跑 OCR（用 ffmpeg 抽帧方案，通常 5-15 分钟）
python ocr_fast.py frames/ temp/

# 2) OCR 完成后，再单独跑 Whisper（无竞争，15-25 分钟）
PYTHONUNBUFFERED=1 python scripts/transcribe.py temp/audio.wav temp/
```

**启动前必做**：杀掉残留的 python 进程，否则旧进程持续吃 CPU：

```powershell
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
```

**韩综/日综中字场景**：OCR 拿到的中文硬字幕是专业翻译，本身已足够产出完整脚本。
Whisper 韩文原文只是可选补充——可让 Whisper 后台跑，同时先基于 OCR 出稿，不要阻塞交付。

### Step 4: 结构化拆解（LLM 分析）

将 Whisper + OCR 的结果交给 LLM 做结构化分析。分析维度：

1. **场景切分**：基于时间间隔 + 语义连贯性，每段含时间区间、主题、要点
2. **内容结构**：开头钩子（Hook）/ 主体内容（Body）/ 行动号召（CTA）
3. **金句提取**：3-5 句最有传播力的句子
4. **话题标签**：5-8 个内容标签

LLM Prompt 模板见 `references/pipeline-guide.md`。

### Step 5: 合并输出

运行 `scripts/merge_output.py`：

```bash
python scripts/merge_output.py <work_dir>
```

**输入**：
- `<work_dir>/temp/transcript.json`（Whisper 转写结果）
- `<work_dir>/temp/subtitles_ocr.json`（OCR 字幕结果）

**输出**（`<work_dir>/output/` 目录下）：

| 文件 | 内容 |
|------|------|
| `{name}_中韩双语.srt` | 双语 SRT（中文在上、韩文在下，可加载到播放器） |
| `{name}_中韩对照.txt` | 纯文本逐行对照 |
| `{name}_中文.srt` | 纯中文 SRT |
| `{name}_韩文.srt` | 纯韩文 SRT |
| `{name}_脚本提取.md` | 完整结构化报告（含对照表格 + 全文） |

**时间轴匹配逻辑**：对每条 OCR 中文字幕，找到时间上重叠的所有 Whisper 段落，拼接为对应的韩文文本。

## 决策指南

### 是否需要 OCR？

| 场景 | 需要 OCR？ | 原因 |
|------|-----------|------|
| 韩综/日综带中文字幕 | ✅ 是 | 硬字幕是专业翻译，质量远超机翻 |
| 纯中文视频（无字幕） | ❌ 否 | Whisper 直接转写中文即可 |
| YouTube 有 CC 字幕 | ❌ 否 | yt-dlp 可直接下载字幕文件 |
| B站无字幕视频 | ❌ 否 | Whisper 转写音轨 |
| B站有硬字幕视频 | ✅ 是 | B站字幕 API 常返回空，需 OCR |

### Whisper 模型选择

| 场景 | 模型 | 速度 | 准确度 |
|------|------|------|--------|
| 快速预览、英文 | `tiny` / `base` | 极快 | 一般 |
| 日常中文短视频 | `small` | 快 | 良好 |
| **中文/韩文（推荐）** | `medium` | 中等 | 优秀 |
| 追求最高准确度 | `large-v3` | 慢 | 最佳 |

## 错误处理

| 问题 | 解决方案 |
|------|----------|
| URL 无法下载 | 尝试 `--cookies-from-browser chrome`；B站可能需要 Referer header |
| Whisper 报 CUDA 错误 | 强制 `device="cpu", compute_type="int8"` |
| RapidOCR conf 类型错误 | `conf = float(conf)` 转换后再比较 |
| B站 subtitle.list 为空 | 说明无官方字幕，需走 OCR 路径 |
| 视频无音轨 | 检查 ffmpeg 提取是否报错，纯画面视频只能 OCR |
| 显存不足 | 降级模型：medium → small → base |
| yt-dlp 未合并视频 | 视频和音频分开存放，分别用于 OCR 和 Whisper |
| **OCR/Whisper 跑了几小时没结果** | 两者并行导致 CPU 争抢 → 改为串行；并先 `Stop-Process -Name python -Force` 清残留进程 |
| **日志停在 loading model 不动** | 首次下载 ~1.5GB 模型属正常；加 `PYTHONUNBUFFERED=1` 才能看到后续进度 |
| **OCR 逐帧读大视频极慢** | 改 ffmpeg 先抽帧成 jpg（`fps=1,scale=640:-1`），再对图片 OCR，快一个数量级 |
| **长视频超时/会话中断后重跑** | 先检查 `temp/` 下是否已有 `subtitles_ocr.*` / `transcript.*`，避免重复劳动 |

## 脚本清单

| 脚本 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `scripts/transcribe.py` | Whisper 语音转写 | audio.wav, output_dir | transcript.json/srt/txt |
| `scripts/ocr_subtitles.py` | OCR 硬字幕提取 | video.mp4, output_dir | subtitles_ocr.json/srt/txt |
| `scripts/extract_audio.py` | 音频提取 | video file | audio.wav |
| `scripts/merge_output.py` | 合并双语输出 | work_dir | 5 个输出文件 |
| `scripts/monitor.py` | 等待 pipeline 完成 | temp_dir | 无（轮询退出） |

## 参考文档

- `references/pipeline-guide.md` — 完整 pipeline 架构、LLM 结构化拆解 prompt 模板、进阶能力
