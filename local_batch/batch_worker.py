#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

UPSTREAM_REPO = "https://github.com/ZY-ZhichaoYu/douyin-transcribe.git"
UPSTREAM_SHA = "e36a495e9c5f11935f6ebdfd08042699442b91b4"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def ensure_upstream(runtime: Path) -> Path:
    dst = runtime / "douyin-transcribe"
    if not (dst / ".git").exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", UPSTREAM_REPO, str(dst)])
    run(["git", "fetch", "--depth", "1", "origin", UPSTREAM_SHA], cwd=dst)
    run(["git", "checkout", "--detach", UPSTREAM_SHA], cwd=dst)
    return dst


def load_upstream(repo: Path):
    spec = importlib.util.spec_from_file_location("douyin_transcribe_upstream", repo / "server.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load upstream server.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_lines(path: Path) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            url, title = line.split("\t", 1)
        else:
            url, title = line, ""
        items.append((url.strip(), title.strip()))
    return items


def stable_id(index: int, url: str) -> str:
    m = re.search(r"/video/(\d+)", url)
    if m:
        return f"{index:03d}_douyin_{m.group(1)}"
    m = re.search(r"(BV[0-9A-Za-z]+)", url)
    if m:
        return f"{index:03d}_bili_{m.group(1)}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{index:03d}_{digest}"


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def acquire_youtube(url: str, out_dir: Path) -> Path:
    out = out_dir / "youtube.%(ext)s"
    run([
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--no-progress",
        "-f",
        "ba/b",
        "-o",
        str(out),
        url,
    ])
    files = [p for p in out_dir.glob("youtube.*") if p.is_file()]
    if not files:
        raise RuntimeError("yt-dlp finished but no media file was created")
    return max(files, key=lambda p: p.stat().st_mtime)


async def acquire_supported(upstream, url: str, out_dir: Path) -> tuple[Path, str]:
    host = re.sub(r"^www\.", "", __import__("urllib.parse").parse.urlparse(url).netloc.lower())
    if host.endswith("youtube.com") or host == "youtu.be":
        loop = asyncio.get_running_loop()
        path = await loop.run_in_executor(None, acquire_youtube, url, out_dir)
        return path, "youtube"

    real_url = upstream._extract_url(url)
    media_path, platform = await upstream._download_transcription_media(real_url, str(out_dir))
    return Path(media_path), platform


def transcribe(repo_root: Path, media: Path, url: str, title: str, ident: str, model: str, output_dir: Path) -> None:
    run([
        sys.executable,
        str(repo_root / "pipeline" / "transcribe_media.py"),
        "--media",
        str(media),
        "--source-url",
        url,
        "--title",
        title or ident,
        "--id",
        ident,
        "--model",
        model,
        "--language",
        "auto",
        "--output-dir",
        str(output_dir),
    ], cwd=repo_root)


async def main_async(args) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    urls_file = Path(args.urls).resolve()
    output_dir = Path(args.output_dir).resolve()
    runtime = Path(args.runtime_dir).resolve()
    state_path = output_dir / "_batch_state.json"

    items = parse_lines(urls_file)
    if not items:
        print(f"No URLs found in {urls_file}")
        return 2

    runtime.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    upstream_repo = ensure_upstream(runtime)
    upstream = load_upstream(upstream_repo)

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}

    ok = skipped = failed = 0
    total = len(items)

    for index, (url, title) in enumerate(items, 1):
        ident = stable_id(index, url)
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        txt = output_dir / f"{ident}.txt"
        jsonl = output_dir / f"{ident}.jsonl"

        if not args.force and state.get(key, {}).get("status") == "ok" and txt.exists() and jsonl.exists():
            skipped += 1
            print(f"[{index}/{total}] SKIP {url}")
            continue

        print(f"[{index}/{total}] START {url}")
        started = time.time()
        try:
            with tempfile.TemporaryDirectory(prefix="batch_media_", dir=str(runtime)) as tmp:
                media, platform = await acquire_supported(upstream, url, Path(tmp))
                transcribe(repo_root, media, url, title, ident, args.model, output_dir)
            state[key] = {
                "status": "ok",
                "url": url,
                "title": title,
                "id": ident,
                "platform": platform,
                "model": args.model,
                "seconds": round(time.time() - started, 1),
                "updated_at": int(time.time()),
            }
            ok += 1
            print(f"[{index}/{total}] OK   {ident}")
        except Exception as exc:
            state[key] = {
                "status": "error",
                "url": url,
                "title": title,
                "id": ident,
                "error": f"{type(exc).__name__}: {exc}",
                "updated_at": int(time.time()),
            }
            failed += 1
            print(f"[{index}/{total}] FAIL {url}\n  {type(exc).__name__}: {exc}")
        finally:
            save_state(state_path, state)

    print("\n=== Batch summary ===")
    print(f"total={total} ok={ok} skipped={skipped} failed={failed}")
    print(f"results={output_dir}")
    return 0 if (ok + skipped) > 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch transcribe Douyin/Bilibili/YouTube URLs locally for free.")
    ap.add_argument("--urls", default="urls.txt")
    ap.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"])
    ap.add_argument("--output-dir", default="results")
    ap.add_argument("--runtime-dir", default=".runtime")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
