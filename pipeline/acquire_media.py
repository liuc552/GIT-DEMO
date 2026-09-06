#!/usr/bin/env python3
"""Acquisition layer.

Input: public page URL + adapter.
Output contract: handoff/manifest.json + handoff/media.<ext>

Acquisition is intentionally separate from ASR. It may run on GitHub-hosted,
self-hosted, desktop, cloud browser, or any future worker. ASR only consumes
its handoff artifact.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"


def copy_to_handoff(src: Path, source_url: str, title: str, ident: str, adapter: str) -> None:
    out_dir = Path("handoff")
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower() or ".media"
    dst = out_dir / f"media{suffix}"
    shutil.copy2(src, dst)
    (out_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "source_url": source_url,
        "title": title,
        "id": ident,
        "adapter": adapter,
        "media_file": dst.name,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "adapter": adapter, "media": str(dst)}, ensure_ascii=False))


def direct(url: str) -> Path:
    suffix = Path(urlparse(url).path).suffix.lower() or ".media"
    tmp = Path(tempfile.mkdtemp(prefix="acq_direct_")) / f"media{suffix}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
        shutil.copyfileobj(r, f)
    return tmp


def ytdlp(url: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="acq_ytdlp_"))
    template = str(tmp_dir / "media.%(ext)s")
    subprocess.run([
        sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "bestaudio/best",
        "--user-agent", UA, "-o", template, url,
    ], check=True)
    files = [p for p in tmp_dir.iterdir() if p.is_file()]
    if not files:
        raise RuntimeError("yt-dlp produced no media")
    return max(files, key=lambda p: p.stat().st_size)


def douyin_open_source(url: str) -> Path:
    """Use ZY-ZhichaoYu/douyin-transcribe as a specialized adapter.

    The upstream project currently imports FastMCP from MCP 1.x, so the
    environment must pin mcp<2. The adapter tries Playwright interception and
    a share-page fallback before downloading a CDN audio/video stream.
    """
    vendor = Path("vendor/douyin-transcribe")
    if not vendor.exists():
        vendor.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "git", "clone", "--depth", "1",
            "https://github.com/ZY-ZhichaoYu/douyin-transcribe.git", str(vendor),
        ], check=True)
    sys.path.insert(0, str(vendor.resolve()))
    from server import _download_transcription_media  # type: ignore

    tmp_dir = tempfile.mkdtemp(prefix="acq_douyin_")
    path, platform = asyncio.run(_download_transcription_media(url, tmp_dir))
    if platform != "douyin":
        raise RuntimeError(f"unexpected platform: {platform}")
    return Path(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--adapter", required=True, choices=["direct", "yt-dlp", "douyin-open-source"])
    ap.add_argument("--title", default="")
    ap.add_argument("--id", default="media")
    args = ap.parse_args()

    if args.adapter == "direct":
        path = direct(args.source_url)
    elif args.adapter == "yt-dlp":
        path = ytdlp(args.source_url)
    else:
        path = douyin_open_source(args.source_url)

    copy_to_handoff(path, args.source_url, args.title, args.id, args.adapter)


if __name__ == "__main__":
    main()
