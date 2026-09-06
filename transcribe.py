import json
from pathlib import Path
from faster_whisper import WhisperModel

WORK = Path('work')
OUT = Path('results')
OUT.mkdir(exist_ok=True)

model = WhisperModel('small', device='cpu', compute_type='int8')

for info_path in sorted(WORK.glob('*.info.json')):
    meta = json.loads(info_path.read_text(encoding='utf-8'))
    vid = str(meta.get('id') or info_path.stem.replace('.info',''))
    title = meta.get('title') or vid
    source_url = meta.get('webpage_url') or meta.get('original_url') or ''
    duration = meta.get('duration')

    candidates = [p for p in WORK.glob(f'{vid}.*') if p.suffix.lower() in {'.mp3','.m4a','.wav','.opus','.webm','.mp4'}]
    if not candidates:
        raise FileNotFoundError(f'No media found for {vid}')
    media = candidates[0]

    segments, info = model.transcribe(
        str(media),
        language='zh',
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=True,
    )
    segments = list(segments)

    jsonl_path = OUT / f'{vid}.jsonl'
    md_path = OUT / f'{vid}.md'

    with jsonl_path.open('w', encoding='utf-8') as f:
        f.write(json.dumps({
            'type':'video', 'id':vid, 'title':title,
            'source_url':source_url, 'duration':duration,
            'language':info.language
        }, ensure_ascii=False) + '\n')
        for i, s in enumerate(segments, 1):
            f.write(json.dumps({
                'type':'segment', 'index':i,
                'start':round(s.start,3), 'end':round(s.end,3),
                'text':s.text.strip()
            }, ensure_ascii=False) + '\n')

    def fmt(sec):
        sec = int(sec)
        return f'{sec//60:02d}:{sec%60:02d}'

    lines = [f'# {title}', '', f'- Source: {source_url}', f'- Duration: {duration}', f'- Detected language: {info.language}', '']
    lines += [f'[{fmt(s.start)}] {s.text.strip()}' for s in segments if s.text.strip()]
    md_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'WROTE {jsonl_path} and {md_path}')
