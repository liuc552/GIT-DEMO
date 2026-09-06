import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi

URL = next(
    line.strip()
    for line in Path('urls.txt').read_text(encoding='utf-8').splitlines()
    if line.strip() and not line.lstrip().startswith('#')
)
VIDEO_ID = parse_qs(urlparse(URL).query).get('v', ['8mQEzS-DXuE'])[0]
TITLE = '中中避战开野区思维讲解｜折纸'
OUT = Path('results')
OUT.mkdir(exist_ok=True)

api = YouTubeTranscriptApi()
transcripts = list(api.list(VIDEO_ID))
print('AVAILABLE_TRANSCRIPTS:')
for t in transcripts:
    print(t.language_code, t.language, 'generated=' + str(t.is_generated))
if not transcripts:
    raise RuntimeError('No YouTube transcript available')

preferred = ['zh-Hans', 'zh-Hant', 'zh-CN', 'zh-TW', 'zh']
chosen = None
for code in preferred:
    chosen = next((t for t in transcripts if t.language_code == code), None)
    if chosen:
        break
if chosen is None:
    chosen = transcripts[0]

fetched = chosen.fetch()
raw = fetched.to_raw_data()
print('CHOSEN:', fetched.language_code, fetched.language, 'generated=', fetched.is_generated)
print('SEGMENTS:', len(raw))

jsonl = OUT / f'{VIDEO_ID}.jsonl'
md = OUT / f'{VIDEO_ID}.md'
with jsonl.open('w', encoding='utf-8') as f:
    f.write(json.dumps({
        'type': 'video', 'id': VIDEO_ID, 'title': TITLE,
        'source_url': URL, 'platform': 'youtube-mirror',
        'transcript_language': fetched.language_code,
        'is_generated': fetched.is_generated,
        'acquisition': 'youtube-transcript-api'
    }, ensure_ascii=False) + '\n')
    for i, x in enumerate(raw, 1):
        text = (x.get('text') or '').replace('\n', ' ').strip()
        if text:
            f.write(json.dumps({
                'type': 'segment', 'index': i,
                'start': round(float(x.get('start', 0)), 3),
                'end': round(float(x.get('start', 0) + x.get('duration', 0)), 3),
                'text': text
            }, ensure_ascii=False) + '\n')

def fmt(sec):
    sec = int(sec)
    return f'{sec//60:02d}:{sec%60:02d}'

lines = [
    f'# {TITLE}', '', f'- Source: {URL}',
    f'- Transcript: {fetched.language} ({fetched.language_code})',
    f'- Auto-generated: {fetched.is_generated}', '',
]
for x in raw:
    text = (x.get('text') or '').replace('\n', ' ').strip()
    if text:
        lines.append(f"[{fmt(float(x.get('start', 0)))}] {text}")
md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(md.read_text(encoding='utf-8'))
