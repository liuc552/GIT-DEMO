# 本地长期免费批量视频转文字

用途：把 `urls.txt` 里的公开视频链接批量转成文字，长期本地免费运行。

当前支持：

- 抖音：长链、短链、分享文本里的链接
- Bilibili：BV 链接、b23.tv 短链
- YouTube：公开视频链接

核心组合：

- 抖音/B站获取：`ZY-ZhichaoYu/douyin-transcribe`（MIT，固定到 commit `e36a495e9c5f11935f6ebdfd08042699442b91b4`）
- YouTube 获取：`yt-dlp`
- ASR：`faster-whisper`
- 输出：TXT + Markdown + JSONL

## 最简单用法（Windows）

1. 把这个仓库放在 D 盘，例如 `D:\video-transcript-pipeline`。
2. 编辑根目录 `urls.txt`，一行一个链接。
3. 双击 `run_batch.bat`。

第一次会自动：

- 创建仓库内 `.venv`
- 安装开源依赖
- 把 Playwright Chromium 下载到仓库内 `.runtime`
- 把 Whisper/HuggingFace 缓存放到仓库内 `.runtime`

后续再次双击即可。

## 输出

`results/` 下每条视频会有：

- `<id>.txt`：纯文字
- `<id>.md`：带时间戳，方便人看
- `<id>.jsonl`：带分段和时间戳，方便 AI 批量分析
- `_batch_state.json`：断点/失败记录

成功过的 URL 默认跳过，所以中途关闭、断网或某条失败后，可以直接重跑，不会把已经完成的全部重新转一遍。

## 可选标题

默认 `urls.txt` 只写 URL 即可。

如果想给某条视频加标题，可以用 TAB 分隔：

```text
https://www.douyin.com/video/123456789	我的标题
```

## 模型

默认 `small`，用于中文研究比较均衡。

如果机器慢，可把 `run_batch.bat` 里的：

```text
--model small
```

改为：

```text
--model base
```

## 隐私与存储

本地转写结果、Whisper 模型、Playwright 浏览器、临时媒体都被 `.gitignore` 排除，不会自动提交到这个公开仓库。

此公开仓库只放通用工具，不放 Northstar、Engineering Brain 或你的私有代码。
