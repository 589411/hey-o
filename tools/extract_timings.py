"""把 yt-dlp 抓下的 YouTube 字幕 (json3) 轉成精簡的逐字時間軸 tools/timings/<videoId>.json
用法：python3 tools/extract_timings.py path/to/<id>.en.json3 [...]
格式：[[毫秒, "word"], ...]（已去掉 [Music]、>>、♪）

自動字幕每個字都有 tOffsetMs；人工字幕只有「一行」的起訖時間，
這時依字長把該行時長分給行內每個字（估計值，足夠拿來對齊句首）。
"""
import json, os, re, sys

for path in sys.argv[1:]:
    vid = os.path.basename(path).split('.')[0]
    d = json.load(open(path))
    out = []
    for e in d.get('events', []):
        base = e.get('tStartMs', 0)
        segs = e.get('segs', []) or []
        words = []  # (ms or None, word)
        for s in segs:
            ws = re.sub(r'\[[^\]]*\]|>>|♪', ' ', s.get('utf8', '')).split()
            for k, w in enumerate(ws):
                words.append((base + s['tOffsetMs'] if k == 0 and 'tOffsetMs' in s else (base if k == 0 and s is segs[0] else None), w))
        if not words:
            continue
        per_word = any('tOffsetMs' in s for s in segs)
        dur = e.get('dDurationMs') or 0
        if not per_word and len(words) > 1 and dur:
            # 人工字幕：依字元數比例分配這一行的時間
            total = sum(len(w) + 1 for _, w in words)
            acc = 0
            for _, w in words:
                out.append([base + round(dur * acc / total), w])
                acc += len(w) + 1
        else:
            last = base
            for ms, w in words:
                last = ms if ms is not None else last
                out.append([last, w])
    dst = os.path.join(os.path.dirname(__file__), 'timings', vid + '.json')
    json.dump(out, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(vid, len(out), 'words')
