"""把 yt-dlp 抓下的 YouTube 自動字幕 (json3) 轉成精簡的逐字時間軸 tools/timings/<videoId>.json
用法：python3 tools/extract_timings.py path/to/<id>.en.json3 [...]
格式：[[毫秒, "word"], ...]（已去掉 [Music] 與 >>）
"""
import json, os, re, sys

for path in sys.argv[1:]:
    vid = os.path.basename(path).split('.')[0]
    d = json.load(open(path))
    out = []
    for e in d.get('events', []):
        base = e.get('tStartMs', 0)
        for s in e.get('segs', []) or []:
            for w in re.sub(r'\[[^\]]*\]|>>', ' ', s.get('utf8', '')).split():
                out.append([base + s.get('tOffsetMs', 0), w])
    dst = os.path.join(os.path.dirname(__file__), 'timings', vid + '.json')
    json.dump(out, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(vid, len(out), 'words')
