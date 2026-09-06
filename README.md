# Public Video → Transcript Worker

Public GitHub Actions worker for research transcription.

- Input: public video URLs from `urls.txt`
- Download: yt-dlp
- Transcription: faster-whisper
- Primary output: JSONL with source metadata + timestamps + segment text
- Human-readable output: Markdown
- Video/audio files are temporary and are not committed
