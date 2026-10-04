"""把 content/*.json（人工校正過的句子＋中譯＋單字）對齊 tools/timings/<videoId>.json（YouTube 字幕逐字時間）
產出 data/lessons.json 給前端用。每句得到 t（開始秒）與 end（結束秒）。

用法：python3 tools/build_data.py
對齊失敗（某句找不到對應字）會印警告並以前後句內插，不會中斷。
"""
import difflib, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUM = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}


def norm(w):
    w = w.lower().replace('’', "'")
    w = re.sub(r"[^a-z0-9']", '', w)
    return w.removesuffix("'s").strip("'")


def toks(text):
    return [n for n in (norm(w) for w in re.split(r"[\s\-—–]+", text)) if n]


def build_lesson(path):
    les = json.load(open(path))
    tpath = os.path.join(ROOT, 'tools', 'timings', les['videoId'] + '.json')
    timing = json.load(open(tpath))
    cap = []  # (ms, token)
    for ms, w in timing:
        for t in toks(w):
            cap.append((ms, t))
    cap_toks = [t for _, t in cap]

    # 全文 token 序列，記下每個 token 屬於哪一句
    lines = les['lines']
    doc, owner = [], []
    for i, (en, *_rest) in enumerate(lines):
        for t in toks(en):
            doc.append(t)
            owner.append(i)

    sm = difflib.SequenceMatcher(None, doc, cap_toks, autojunk=False)
    first = [None] * len(lines)   # 每句第一個對上的字的 ms
    last = [None] * len(lines)
    matched = [0] * len(lines)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            i = owner[a + k]
            ms = cap[b + k][0]
            # 句首字若被跳過，用第一個對上的字往前推一點
            if first[i] is None:
                first[i] = ms
            last[i] = ms
            matched[i] += 1

    total_words = [len(toks(l[0])) for l in lines]
    dur = les.get('duration') or (timing[-1][0] / 1000 + 3)
    out = []
    for i, (en, zh, vocab) in enumerate(lines):
        ratio = matched[i] / max(1, total_words[i])
        if first[i] is None or ratio < 0.4:
            print(f"  ⚠ {les['id']} #{i} 對齊率 {ratio:.0%}：{en[:50]}")
        out.append({'en': en, 'zh': zh, 'vocab': [dict(zip(['form', 'lemma', 'pos', 'ipa', 'zh'], v)) for v in vocab],
                    't': None if first[i] is None else first[i] / 1000})
    # 缺漏內插
    for i, o in enumerate(out):
        if o['t'] is None:
            prev = next((out[j]['t'] for j in range(i - 1, -1, -1) if out[j]['t'] is not None), 0)
            o['t'] = prev + 0.5
    # 單調化（避免對錯造成倒退）
    for i in range(1, len(out)):
        if out[i]['t'] < out[i - 1]['t']:
            print(f"  ⚠ {les['id']} #{i} 時間倒退，已修正")
            out[i]['t'] = out[i - 1]['t'] + 0.5
    for i, o in enumerate(out):
        # 句尾：最後一個對上的字 + 0.9 秒緩衝，但不超過下一句開頭
        nxt = out[i + 1]['t'] if i + 1 < len(out) else dur
        end_guess = (last[i] / 1000 + 0.9) if last[i] else nxt
        o['end'] = round(min(max(end_guess, o['t'] + 1.0), nxt), 2)
        o['t'] = round(max(0, o['t'] - 0.15), 2)
    les['lines'] = out
    les['duration'] = round(dur)
    return les


def main():
    lessons = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'content', '*.json'))):
        print('▸', os.path.basename(p))
        lessons.append(build_lesson(p))
    dst = os.path.join(ROOT, 'data', 'lessons.json')
    json.dump({'version': 1, 'lessons': lessons}, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'✓ {len(lessons)} 課、{sum(len(l["lines"]) for l in lessons)} 句 → data/lessons.json')


if __name__ == '__main__':
    main()
