# Pipeline 详细指南

## 完整 Pipeline 架构

### 输入输出规格

**输入**：视频链接（YouTube / B站 / 抖音 / TikTok / 小红书 / Twitter/X / 西瓜视频等）或本地视频文件路径。

**输出**：结构化 Markdown 脚本文稿 + 双语 SRT 字幕，包含：
1. 视频元信息（标题、作者、时长、来源平台）
2. 带时间戳的完整逐字文稿
3. 按场景/话题切分的结构化拆解
4. 内容结构分析（开头钩子、主体内容、行动号召）
5. 金句摘录 & 关键话题标签
6. 中韩/中英双语对照 SRT（如适用）

---

## yt-dlp 下载要点

### 支持的站点
- YouTube、B站（bilibili.com）、抖音（douyin.com）、TikTok
- 小红书、微博视频、西瓜视频、优酷、腾讯视频
- Twitter/X、Instagram、Facebook、Vimeo

### 下载命令

```bash
yt-dlp -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
  --merge-output-format mp4 \
  -o "%(title).80s.%(ext)s" \
  --write-info-json \
  --no-playlist \
  "URL"
```

### 特殊处理
- B站/部分站点可能需要 cookies：`--cookies-from-browser chrome` 或 `--cookies cookies.txt`
- 抖音/TikTok 短链接需先 resolve 重定向
- B站下载后视频和音频可能分开（`.mp4` + `.m4a`），无需合并——分别用于 OCR 和 Whisper

### 元信息提取

```python
metadata = {
    "title": info.get("title", ""),
    "uploader": info.get("uploader", ""),
    "duration": info.get("duration", 0),
    "platform": info.get("extractor_key", ""),
    "url": url,
    "upload_date": info.get("upload_date", ""),
    "view_count": info.get("view_count", 0),
    "description": info.get("description", ""),
}
```

---

## LLM 结构化拆解 Prompt 模板

将逐字文稿交给 LLM 做结构化分析时使用以下 prompt：

```
你是一个专业的视频内容分析师。请对以下视频转写文稿进行结构化拆解。

## 视频信息
- 标题：{title}
- 作者：{uploader}
- 时长：{duration}秒
- 平台：{platform}

## 逐字文稿（带时间戳）
{transcript}

## 请输出以下 JSON 结构（严格按此格式，不要多余文字）：

{
  "scenes": [
    {
      "index": 1,
      "time_range": "00:00-00:15",
      "topic": "场景主题（5-10字）",
      "text": "该场景完整文本",
      "key_points": ["要点1", "要点2"]
    }
  ],
  "structure": {
    "hook": {
      "time_range": "00:00-00:12",
      "text": "开头钩子内容",
      "tactic": "使用的吸引手法（如：提问/反常识/悬念/数据冲击）"
    },
    "body": {
      "time_range": "00:12-02:30",
      "summary": "主体内容概述（2-3句）",
      "main_arguments": ["论点1", "论点2", "论点3"]
    },
    "cta": {
      "time_range": "02:30-02:45",
      "text": "行动号召内容",
      "type": "关注/点赞/购买/订阅/分享/其他"
    }
  },
  "golden_quotes": [
    "金句1",
    "金句2",
    "金句3"
  ],
  "tags": ["标签1", "标签2", "标签3"],
  "summary": "整条视频的一句话概括"
}
```

---

## Markdown 输出格式

最终输出格式模板：

```markdown
# {视频标题}

> **作者**：{uploader}  
> **平台**：{platform}  
> **时长**：{duration}  
> **来源**：{url}  
> **发布日期**：{upload_date}

## 📋 一句话概括
{summary}

## 🏷️ 话题标签
{#标签1} {#标签2} {#标签3} ...

## ✨ 金句摘录
1. {金句1}
2. {金句2}
3. {金句3}

## 📐 内容结构

### 🪝 开头钩子（{hook.time_range}）
**手法**：{hook.tactic}

> {hook.text}

### 📖 主体内容（{body.time_range}）
{body.summary}

**核心论点**：
1. {main_arguments[0]}
2. {main_arguments[1]}
3. {main_arguments[2]}

### 📢 行动号召（{cta.time_range}）
**类型**：{cta.type}

> {cta.text}

## 🎬 逐场景拆解

### 场景 1：{scenes[0].topic}
**时间**：{scenes[0].time_range}

{scenes[0].text}

**要点**：
- {scenes[0].key_points[0]}
- {scenes[0].key_points[1]}

---

## 📝 完整逐字文稿

[00:00] {第一句转写文本}
[00:05] {第二句转写文本}
...

---

*由 Video Script Extractor 自动生成 | {生成时间}*
```

---

## 进阶能力

### 1. 多说话人识别（Speaker Diarization）
- 用 `pyannote.audio` 区分不同说话人
- 输出格式：`[00:15] 说话人A: ...`

### 2. 画面关键帧提取
- 用 ffmpeg 按场景变化提取关键帧
- 配合文稿做"图文对照"

### 3. 情感分析
- 对每个场景标注情绪（积极/中性/消极/激动）

### 4. 竞品对比模式
- 输入多个同类视频，横向对比结构差异

### 5. 一键改写
- 基于拆解结果，生成同主题的新脚本框架

---

## 验收标准

1. **YouTube 短视频**（<5 分钟中文）→ 完整跑通，文稿准确率 >90%
2. **B站长视频**（20-40 分钟）→ 完整跑通，场景切分合理
3. **抖音短视频**（<1 分钟）→ 完整跑通，结构分析到位
4. **本地 mp4 文件** → 完整跑通
5. **英文视频** → 语言自动检测，英文转写正常
6. **无音轨视频** → 优雅报错，不崩溃
7. **韩综带中文字幕** → OCR + Whisper 双路并行，双语对照输出
