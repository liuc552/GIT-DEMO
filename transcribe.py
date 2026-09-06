import json
from pathlib import Path
from faster_whisper import WhisperModel

URL = next(
    line.strip()
    for line in Path("urls.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
)
TITLE = "中中避战开野区思维讲解｜折纸"
VIDEO_ID = "7651868438474057573"
OUT = Path("results")
OUT.mkdir(exist_ok=True)

media_files = []
for ext in ("*.mp4", "*.webm", "*.m4a", "*.mp3", "*.wav", "*.opus"):
    media_files.extend(Path("work").rglob(ext))
if not media_files:
    raise FileNotFoundError("F2 did not produce a media file")
media_path = sorted(media_files, key=lambda p: p.stat().st_size, reverse=True)[0]
print("Using media:", media_path)

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    str(media_path), language="zh", vad_filter=True, beam_size=5,
    condition_on_previous_text=True,
)
segments = list(segments)

def fmt(sec: float) -> str:
    total = int(sec)
    return f"{total // 60:02d}:{total % 60:02d}"

jsonl_path = OUT / f"{VIDEO_ID}.jsonl"
md_path = OUT / f"{VIDEO_ID}.md"
with jsonl_path.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "type": "video", "id": VIDEO_ID, "title": TITLE,
        "source_url": URL, "platform": "douyin",
        "language": info.language,
        "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
        "model": "faster-whisper-small",
    }, ensure_ascii=False) + "\n")
    for i, seg in enumerate(segments, 1):
        text = seg.text.strip()
        if text:
            f.write(json.dumps({
                "type": "segment", "index": i,
                "start": round(float(seg.start), 3),
                "end": round(float(seg.end), 3), "text": text,
            }, ensure_ascii=False) + "\n")

lines = [
    f"# {TITLE}", "", f"- Source: {URL}",
    "- Acquisition: F2", "- Model: faster-whisper-small", "",
]
lines += [f"[{fmt(s.start)}] {s.text.strip()}" for s in segments if s.text.strip()]
md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"segments={len(segments)} language={info.language}")
print(md_path.read_text(encoding="utf-8"))
