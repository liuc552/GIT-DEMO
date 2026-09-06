import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "vendor/douyin-transcribe")
from server import _download_transcription_media  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

URL = next(
    line.strip()
    for line in Path("urls.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
)
TITLE = "中中避战开野区思维讲解｜折纸"
VIDEO_ID = "7651868438474057573"
OUT = Path("results")
OUT.mkdir(exist_ok=True)


def fmt(sec: float) -> str:
    total = int(sec)
    return f"{total // 60:02d}:{total % 60:02d}"


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="zhezhi_") as tmp:
        media_path, platform = await _download_transcription_media(URL, tmp)
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            media_path,
            language="zh",
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=True,
        )
        segments = list(segments)

        jsonl_path = OUT / f"{VIDEO_ID}.jsonl"
        md_path = OUT / f"{VIDEO_ID}.md"

        with jsonl_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({
                "type": "video",
                "id": VIDEO_ID,
                "title": TITLE,
                "source_url": URL,
                "platform": platform,
                "language": info.language,
                "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
                "model": "faster-whisper-small",
            }, ensure_ascii=False) + "\n")
            for i, seg in enumerate(segments, 1):
                text = seg.text.strip()
                if not text:
                    continue
                f.write(json.dumps({
                    "type": "segment",
                    "index": i,
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": text,
                }, ensure_ascii=False) + "\n")

        lines = [
            f"# {TITLE}",
            "",
            f"- Source: {URL}",
            f"- Platform: {platform}",
            f"- Model: faster-whisper-small",
            "",
        ]
        lines.extend(
            f"[{fmt(seg.start)}] {seg.text.strip()}"
            for seg in segments
            if seg.text.strip()
        )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(f"segments={len(segments)} language={info.language}")
        print(md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
