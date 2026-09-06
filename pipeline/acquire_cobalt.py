#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

VIDEO_URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=8mQEzS-DXuE"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "work/zhezhi-one.media")
OUT.parent.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/json"})


def candidate_instances():
    # Try the canonical hosted endpoint first, then community instances.
    seen = set()
    candidates = ["https://api.cobalt.tools"]
    try:
        r = S.get("https://instances.cobalt.best/api/instances.json", timeout=20)
        r.raise_for_status()
        data = r.json()
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("api")
            online = item.get("online") or {}
            if isinstance(online, dict) and online.get("api") is False:
                continue
            if url:
                candidates.append(url.rstrip("/"))
    except Exception as e:
        print(f"instance-list warning: {e}")
    for c in candidates:
        c = c.rstrip("/")
        if c and c not in seen:
            seen.add(c)
            yield c


def download(url: str, dst: Path):
    with S.get(url, stream=True, timeout=(20, 300), allow_redirects=True) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        total = 0
        with dst.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
        if total < 100_000:
            raise RuntimeError(f"download too small: {total} bytes, content-type={ctype}")
        print(f"downloaded {total} bytes from {r.url} content-type={ctype}")


def process(instance: str):
    payload = {
        "url": VIDEO_URL,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "audioBitrate": "128",
        "filenameStyle": "basic",
    }
    print(f"trying cobalt instance: {instance}")
    r = S.post(instance + "/", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    status = data.get("status")
    print("status:", status)
    if status in ("tunnel", "redirect"):
        media_url = data.get("url")
        if not media_url:
            raise RuntimeError("missing media url")
        download(media_url, OUT)
        return data
    if status == "picker":
        # Audio-only requests normally don't return picker, but handle a media URL if present.
        for item in data.get("picker", []):
            if isinstance(item, dict) and item.get("url"):
                try:
                    download(item["url"], OUT)
                    return data
                except Exception:
                    pass
        raise RuntimeError("picker returned no downloadable item")
    if status == "error":
        err = data.get("error", {})
        raise RuntimeError(json.dumps(err, ensure_ascii=False))
    raise RuntimeError(f"unsupported cobalt response: {json.dumps(data, ensure_ascii=False)[:500]}")


errors = []
for instance in candidate_instances():
    try:
        meta = process(instance)
        Path("work/acquisition.json").write_text(json.dumps({
            "source_url": VIDEO_URL,
            "adapter": "cobalt",
            "instance": instance,
            "response_status": meta.get("status"),
            "media_file": str(OUT),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ACQUIRED via {instance}: {OUT} ({OUT.stat().st_size} bytes)")
        sys.exit(0)
    except Exception as e:
        msg = f"{instance}: {type(e).__name__}: {e}"
        print("failed:", msg)
        errors.append(msg)

print("all cobalt instances failed")
for e in errors[-12:]:
    print(" -", e)
sys.exit(2)
