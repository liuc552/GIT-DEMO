# Video Transcript Pipeline — Decoupled Architecture

This repository is a public worker only. It must not contain private source code, Northstar research, Engineering Brain material, or private transcripts.

## Pipeline

```text
Public source page
      |
      v
[ Acquisition adapter ]  <-- platform-specific, failure-prone
      |
      |  media-handoff artifact
      |  - manifest.json
      |  - media.*
      v
[ ASR Worker ]           <-- platform-agnostic, stable
      |
      +--> <id>.txt      human/plain text
      +--> <id>.md       readable timestamps + metadata
      +--> <id>.jsonl    AI-native segment corpus
      v
Transcript artifact
      |
      v
Northstar analysis (outside this public repo)
```

## Contract boundary

Acquisition succeeds only when it emits `handoff/manifest.json` plus a playable `handoff/media.*` containing an audio stream. It does not perform ASR.

ASR accepts either:

1. a local media file from the handoff artifact, or
2. a **direct downloadable media URL**.

ASR never parses Douyin/YouTube pages and never needs platform cookies.

## Acquisition adapters

- `direct`: direct audio/video URL.
- `yt-dlp`: generic public page extraction.
- `douyin-open-source`: specialized Playwright/share-page fallback using `ZY-ZhichaoYu/douyin-transcribe` with `mcp<2` pinned.

These adapters may run anywhere: GitHub-hosted runner, self-hosted runner, desktop, cloud browser, or a future acquisition service. Changing an adapter must not require changing ASR.

## GitHub Actions

- `Acquire Media`: page URL -> one-day `media-handoff` artifact.
- `ASR Worker`: automatically consumes a successful `Acquire Media` run, or can be dispatched with a direct media URL.
- `ASR Selftest`: generates known speech locally and proves ASR works independently of all external video platforms.

## Output policy

Transcripts are uploaded as short-lived GitHub Actions artifacts and are **not committed into the public repository**. The public repository contains only generic tooling.
