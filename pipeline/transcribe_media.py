#!/usr/bin/env python3
"""Pure ASR worker: media file or direct media URL -> TXT/MD/JSONL.

This module deliberately knows nothing about Douyin/YouTube page extraction.
Its only contract is: give me playable media with an audio stream.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"


def safe_id(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    return value[:120] or "media"


def download_direct(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".mp4", ".webm", ".mov", ".mkv"}:
        suffix = ".media"
    out = out_dir / f"input{suffix}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=120) as r, out.open("wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("direct media download produced an empty file")
    return out


def probe_audio(path: Path) -> None:
    """Verify that media contains audio without requiring a system ffmpeg install."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "json", str(path)],
            text=True, capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()[-500:]}")
        data = json.loads(proc.stdout or "{}")
        if not data.get("streams"):
            raise RuntimeError("media contains no audio stream")
        return

    import av
    try:
        with av.open(str(path)) as container:
            if not any(stream.type == "audio" for stream in container.streams):
                raise RuntimeError("media contains no audio stream")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"cannot inspect media audio stream: {exc}") from exc


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt(sec: float) -> str:
    total = max(0, int(sec))
    return f"{total // 60:02d}:{total % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--media", help="Local media file")
    group.add_argument("--media-url", help="Direct downloadable media URL (not a webpage)")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"])
    ap.add_argument("--language", default="zh")
    ap.add_argument("--output-dir", default="results")
    args = ap.parse_args()

    work = Path("work")
    media = Path(args.media) if args.media else download_direct(args.media_url, work)
    if not media.exists():
        raise FileNotFoundError(media)
    probe_audio(media)

    media_hash = sha256(media)
    ident = safe_id(args.id or media_hash[:16])
    title = args.title or ident
    source_url = args.source_url or args.media_url or ""

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(
        str(media),
        language=None if args.language == "auto" else args.language,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=True,
    )
    segments = [s for s in segments_iter if s.text.strip()]

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    txt_path = out / f"{ident}.txt"
    md_path = out / f"{ident}.md"
    jsonl_path = out / f"{ident}.jsonl"

    plain = "\n".join(s.text.strip() for s in segments) + "\n"
    txt_path.write_text(plain, encoding="utf-8")

    md_lines = [f"# {title}", "", f"- Source: {source_url or 'unknown'}", f"- Model: faster-whisper-{args.model}", f"- Media SHA256: `{media_hash}`", ""]
    md_lines.extend(f"[{fmt(float(s.start))}] {s.text.strip()}" for s in segments)
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    with jsonl_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "video",
            "id": ident,
            "title": title,
            "source_url": source_url,
            "media_sha256": media_hash,
            "language": getattr(info, "language", args.language),
            "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
            "model": f"faster-whisper-{args.model}",
        }, ensure_ascii=False) + "\n")
        for index, s in enumerate(segments, 1):
            f.write(json.dumps({
                "type": "segment",
                "index": index,
                "start": round(float(s.start), 3),
                "end": round(float(s.end), 3),
                "text": s.text.strip(),
            }, ensure_ascii=False) + "\n")

    print(json.dumps({"status": "ok", "id": ident, "segments": len(segments), "results": [str(txt_path), str(md_path), str(jsonl_path)]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
