"""把 content/<series>/*.json（人工校正過的句子＋中譯＋單字）對齊 tools/timings/<videoId>.json（YouTube 字幕逐字時間）
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


def align(lines, video_id, clip=None):
    """把句子對齊字幕逐字時間。回傳每句第一/最後對上的 ms、對上字數、句子字數，與字幕覆蓋率。
    clip=(startSec, endSec)：長片切段時只拿這段字幕來對（前後各放寬 2 秒）。"""
    timing = json.load(open(os.path.join(ROOT, 'tools', 'timings', video_id + '.json')))
    if clip:
        lo, hi = (clip[0] - 2) * 1000, (clip[1] + 2) * 1000
        timing = [x for x in timing if lo <= x[0] <= hi]
    cap = []  # (ms, token)
    for ms, w in timing:
        for t in toks(w):
            cap.append((ms, t))
    cap_toks = [t for _, t in cap]

    # 全文 token 序列，記下每個 token 屬於哪一句
    doc, owner = [], []
    for i, (en, *_rest) in enumerate(lines):
        for t in toks(en):
            doc.append(t)
            owner.append(i)

    sm = difflib.SequenceMatcher(None, doc, cap_toks, autojunk=False)
    first = [None] * len(lines)   # 每句第一個對上的字的 ms
    last = [None] * len(lines)
    matched = [0] * len(lines)
    cap_hit = 0
    for a, b, size in sm.get_matching_blocks():
        cap_hit += size
        for k in range(size):
            i = owner[a + k]
            ms = cap[b + k][0]
            if first[i] is None:
                first[i] = ms
            last[i] = ms
            matched[i] += 1
    total_words = [len(toks(l[0])) for l in lines]
    return {'timing': timing, 'first': first, 'last': last, 'matched': matched,
            'total_words': total_words, 'caption_coverage': cap_hit / max(1, len(cap_toks)),
            'text_fidelity': sum(matched) / max(1, sum(total_words))}


def build_lesson(path):
    les = json.load(open(path))
    lines = les['lines']
    clip = (les['clipStart'], les['clipEnd']) if 'clipStart' in les else None
    al = align(lines, les['videoId'], clip)
    timing, first, last, matched = al['timing'], al['first'], al['last'], al['matched']

    total_words = al['total_words']
    dur = clip[1] if clip else (les.get('duration') or (timing[-1][0] / 1000 + 3))
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
    les['duration'] = round(dur - clip[0]) if clip else round(dur)
    return les


BOOKS = '創世記 出埃及記 利未記 民數記 申命記 約書亞記 士師記 路得記 撒母耳記上 撒母耳記下 列王紀上 列王紀下 歷代志上 歷代志下 以斯拉記 尼希米記 以斯帖記 約伯記 詩篇 箴言 傳道書 雅歌 以賽亞書 耶利米書 耶利米哀歌 以西結書 但以理書 何西阿書 約珥書 阿摩司書 俄巴底亞書 約拿書 彌迦書 那鴻書 哈巴谷書 西番雅書 哈該書 撒迦利亞書 瑪拉基書 馬太福音 馬可福音 路加福音 約翰福音 使徒行傳 羅馬書 哥林多前書 哥林多後書 加拉太書 以弗所書 腓立比書 歌羅西書 帖撒羅尼迦前書 帖撒羅尼迦後書 提摩太前書 提摩太後書 提多書 腓利門書 希伯來書 雅各書 彼得前書 彼得後書 約翰一書 約翰二書 約翰三書 猶大書 啟示錄'.split()


def bible_order(les):
    """依 ref（例：「出埃及記 32–34」）排聖經順序；認不得的排最後。"""
    m = re.match(r'(\S+)\s*(\d+)?', les.get('ref', ''))
    book = m.group(1) if m else ''
    idx = BOOKS.index(book) if book in BOOKS else len(BOOKS)
    return (idx, int(m.group(2)) if m and m.group(2) else 0)


def load_series():
    return json.load(open(os.path.join(ROOT, 'content', 'series.json')))


def main():
    series = load_series()
    lessons = []
    for se in series:
        group = []
        for p in sorted(glob.glob(os.path.join(ROOT, 'content', se['id'], '*.json'))):
            print('▸', se['id'] + '/' + os.path.basename(p))
            les = build_lesson(p)
            les['series'] = se['id']
            group.append(les)
        if se.get('order') == 'bible':
            group.sort(key=bible_order)   # 其他系列照檔名（content/<series>/NN-…）排序
        se['count'] = len(group)
        lessons += group
    dst = os.path.join(ROOT, 'data', 'lessons.json')
    pub = [{k: v for k, v in se.items() if not k.startswith('min') and k != 'channel'} for se in series]
    json.dump({'version': 2, 'series': pub, 'lessons': lessons}, open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(f'✓ {len(series)} 系列、{len(lessons)} 課、{sum(len(l["lines"]) for l in lessons)} 句 → data/lessons.json')


if __name__ == '__main__':
    main()
