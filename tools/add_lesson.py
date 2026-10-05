"""擴充課程：yt-dlp 抓真字幕（確定性）→ agy 斷句/中譯/選單字（LLM）→ 程式驗證 → 寫 content/ 並重建 data。

用法：
  python3 tools/add_lesson.py --list                 # 列出頻道上還沒收錄的 Hey-O / Stories of the Bible 單集
  python3 tools/add_lesson.py <videoId> [<videoId>…]  # 新增一課或多課
    --model "Gemini 3.1 Pro (High)"   agy 模型（agy models 可看清單）
    --keep-going                      某支失敗時繼續處理下一支

分工原則：影片 ID、字幕、時間軸一律來自 YouTube（不讓 LLM 碰）；agy 只負責「把字幕改寫成乾淨句子＋中譯＋單字」。
agy 的輸出要通過 fidelity / coverage 檢查才會寫入（擋住 LLM 編句子或漏段落）。

需要：yt-dlp（brew install yt-dlp，或用環境變數 YTDLP 指向）、agy（Antigravity CLI，已登入）。
"""
import argparse, glob, json, os, re, subprocess, sys, time, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_data  # noqa: E402

YTDLP = os.environ.get('YTDLP', 'yt-dlp')
AGY = os.environ.get('AGY', 'agy')
CHANNEL = 'https://www.youtube.com/@SaddlebackKids/videos'
CACHE = os.path.join(ROOT, 'tools', '.cache')
MIN_FIDELITY, MIN_COVERAGE, MIN_LINE = 0.90, 0.85, 0.5


def log(*a):
    print(*a, flush=True)


# ---------- 1. YouTube（確定性） ----------
def existing_ids():
    return {json.load(open(p))['videoId'] for p in glob.glob(os.path.join(ROOT, 'content', '*.json'))}


def list_candidates():
    out = subprocess.run([YTDLP, '--flat-playlist', '--print', '%(id)s|%(title)s', CHANNEL],
                         capture_output=True, text=True).stdout
    have = existing_ids()
    rows = []
    for line in out.splitlines():
        vid, _, title = line.partition('|')
        if re.search(r'Stories of the Bible\s*$', title) and not re.search(r'Church at Home|Available Now|Book Release', title):
            rows.append((vid, title, vid in have))
    for vid, title, done in rows:
        log(f"{'✓' if done else ' '} {vid}  {title}")
    log(f"\n共 {len(rows)} 支，已收錄 {sum(d for *_, d in rows)} 支。用法：python3 tools/add_lesson.py <videoId>")


def oembed(vid):
    url = 'https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote(f'https://www.youtube.com/watch?v={vid}')
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def fetch_captions(vid):
    """抓英文自動字幕 json3 + info。ios client 才拿得到；429 就退避重試。"""
    os.makedirs(CACHE, exist_ok=True)
    sub, info = os.path.join(CACHE, f'{vid}.en.json3'), os.path.join(CACHE, f'{vid}.info.json')
    for attempt in range(4):
        if os.path.exists(sub) and os.path.exists(info):
            return sub, json.load(open(info))
        r = subprocess.run([YTDLP, '--extractor-args', 'youtube:player_client=ios', '--ignore-no-formats-error',
                            '--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', 'en',
                            '--sub-format', 'json3', '--write-info-json', '-o', os.path.join(CACHE, '%(id)s'),
                            f'https://www.youtube.com/watch?v={vid}'], capture_output=True, text=True)
        if os.path.exists(sub) and os.path.exists(info):
            return sub, json.load(open(info))
        if '429' in r.stdout + r.stderr:
            wait = 60 * (attempt + 1)
            log(f'  YouTube 429 限流，{wait} 秒後重試…')
            time.sleep(wait)
        else:
            raise RuntimeError('抓字幕失敗：' + (r.stderr.strip().splitlines() or ['?'])[-1])
    raise RuntimeError('YouTube 持續 429，晚點再試')


def save_timings(vid, sub_path):
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'extract_timings.py'), sub_path], check=True, capture_output=True)
    words = json.load(open(os.path.join(ROOT, 'tools', 'timings', vid + '.json')))
    return ' '.join(w for _, w in words)


# ---------- 2. agy（LLM） ----------
PROMPT = """You are preparing an English listening/speaking lesson for Taiwanese learners from a kids' Bible cartoon.
Below is the RAW YouTube auto-caption text of the video "{title}" (no punctuation, may contain recognition errors).

Your job: rewrite it into clean sentences, translate, and pick vocabulary. Output ONLY one JSON object, no markdown fences, no commentary. Do NOT use any tools or read/write any files.

Rules:
1. Keep the narrator's ACTUAL words in order. Only add punctuation/capitalization, split into sentences, and fix obvious speech-recognition errors (especially Bible names, e.g. "II" -> "Eve", "Cicora" -> "Sisera"). Do NOT paraphrase, summarize, add, or reorder content.
2. Drop the opening "Hey-O / Stories of the Bible / <title>" intro and meaningless fillers like "hey", "wow", "hmm", "oh", "okay", "yeah", "you", "foreign". Keep everything else.
3. One sentence per line; split very long run-ons at natural clause boundaries. Quoted speech uses double quotes.
4. "zh": natural Traditional Chinese (Taiwan). Bible names/places use 和合本 (Chinese Union Version) translations, e.g. Moses 摩西, Aaron 亞倫, Joseph 約瑟, Cain 該隱, Abel 亞伯. Always write God as 「神」 (never 「上帝」), and use 祂 for God/Jesus.
5. "vocab": 0–3 useful words per sentence for an intermediate learner (skip trivial words and proper names). Each item is [form, lemma, pos, ipa, zh]:
   - form: the word/phrase EXACTLY as it appears in that sentence's "en" (same spelling/inflection, case-sensitive)
   - lemma: dictionary form; pos: one of n. v. adj. adv. prep. conj. phr.; ipa: American IPA in slashes; zh: short Traditional Chinese meaning
6. "titleZh": Chinese lesson title. "ref": the Bible passage in Chinese book names, e.g. "創世記 4".

Output schema (exactly these keys):
{{"titleZh": "...", "ref": "...", "lines": [["English sentence.", "中文翻譯。", [["form","lemma","pos","/ipa/","中文"]]], ...]}}

Example of two lines in the expected style:
{example}

RAW CAPTION TEXT:
{raw}
"""


def example_lines():
    les = json.load(open(sorted(glob.glob(os.path.join(ROOT, 'content', '*.json')))[0]))
    return json.dumps(les['lines'][1:3], ensure_ascii=False)


def call_agy(prompt, model, timeout_min=8):
    cmd = [AGY, '-p', prompt, '--print-timeout', f'{timeout_min}m', '--sandbox']
    if model:
        cmd += ['--model', model]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_min * 60 + 60, cwd=CACHE)
    out = r.stdout.strip()
    m = re.search(r'\{.*\}', out, re.S)  # 容忍前後雜訊或 ``` 圍欄
    if not m:
        raise RuntimeError('agy 沒有回傳 JSON：' + (out[-300:] or r.stderr[-300:]))
    return json.loads(m.group(0))


# ---------- 3. 驗證 ----------
POS = {'n.', 'v.', 'adj.', 'adv.', 'prep.', 'conj.', 'phr.', 'n./adj.', 'pron.', 'int.'}


def validate(draft, vid):
    errs = []
    for k in ('titleZh', 'ref', 'lines'):
        if not draft.get(k):
            errs.append(f'缺欄位 {k}')
    lines = draft.get('lines') or []
    for i, ln in enumerate(lines):
        if not (isinstance(ln, list) and len(ln) == 3 and isinstance(ln[0], str) and isinstance(ln[1], str) and isinstance(ln[2], list)):
            errs.append(f'#{i} 格式錯誤'); continue
        if not re.search(r'[一-鿿]', ln[1]):
            errs.append(f'#{i} 沒有中文翻譯')
        for v in ln[2]:
            if not (isinstance(v, list) and len(v) == 5):
                errs.append(f'#{i} 單字格式錯誤 {v}'); continue
            if not re.search(r'(?<![A-Za-z])' + re.escape(v[0]) + r'(?![A-Za-z])', ln[0]):
                errs.append(f'#{i} 單字 "{v[0]}" 不在句子裡')
            if v[2] not in POS:
                errs.append(f'#{i} 詞性 "{v[2]}" 不合法')
    if errs:
        return errs, None
    al = build_data.align(lines, vid)
    stats = {'fidelity': al['text_fidelity'], 'coverage': al['caption_coverage']}
    if stats['fidelity'] < MIN_FIDELITY:
        errs.append(f"英文與字幕吻合度 {stats['fidelity']:.0%} < {MIN_FIDELITY:.0%}（疑似改寫/編造）")
    if stats['coverage'] < MIN_COVERAGE:
        errs.append(f"字幕覆蓋率 {stats['coverage']:.0%} < {MIN_COVERAGE:.0%}（疑似漏段落）")
    for i, (m, t) in enumerate(zip(al['matched'], al['total_words'])):
        if m / max(1, t) < MIN_LINE:
            errs.append(f'#{i} 對不上字幕（{m}/{t}）：{lines[i][0][:60]}')
    return errs, stats


# ---------- 4. 寫入 ----------
def slug(title):
    t = re.split(r'\s*[|(]', title)[0].replace("'s ", 's ').replace("’s ", 's ')
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:40]


def write_lesson(vid, info, draft):
    files = sorted(glob.glob(os.path.join(ROOT, 'content', '*.json')))
    nums = [int(os.path.basename(p)[:2]) for p in files if os.path.basename(p)[:2].isdigit()]
    num = max(nums, default=0) + 1
    title = re.split(r'\s*[|(]', info['title'])[0].strip()
    les = {'id': slug(info['title']), 'videoId': vid, 'title': title, 'titleZh': draft['titleZh'],
           'ref': draft['ref'], 'duration': int(info.get('duration') or 0), 'lines': draft['lines']}
    if any(json.load(open(p))['id'] == les['id'] for p in files):
        les['id'] += '-' + vid[:4].lower()
    path = os.path.join(ROOT, 'content', f'{num:02d}-{les["id"]}.json')
    with open(path, 'w') as f:
        f.write('{\n')
        for k in ('id', 'videoId', 'title', 'titleZh', 'ref', 'duration'):
            f.write(f'  {json.dumps(k)}: {json.dumps(les[k], ensure_ascii=False)},\n')
        f.write('  "lines": [\n' + ',\n'.join('    ' + json.dumps(l, ensure_ascii=False) for l in les['lines']) + '\n  ]\n}\n')
    return path


def bump_sw():
    p = os.path.join(ROOT, 'sw.js')
    s = open(p).read()
    s2 = re.sub(r"hey-o-v(\d+)", lambda m: f'hey-o-v{int(m.group(1)) + 1}', s, count=1)
    open(p, 'w').write(s2)


def add(vid, model):
    log(f'▸ {vid}')
    if vid in existing_ids():
        log('  已收錄，跳過'); return False
    meta = oembed(vid)
    if not meta:
        raise RuntimeError('YouTube 查無此影片（ID 錯誤或已下架）')
    if 'Saddleback' not in meta.get('author_name', ''):
        log(f"  ⚠ 頻道是「{meta.get('author_name')}」，不是 Saddleback Kids")
    log(f"  影片：{meta['title']}")
    sub, info = fetch_captions(vid)
    if not info.get('playable_in_embed', True):
        raise RuntimeError('這支影片禁止嵌入播放')
    raw = save_timings(vid, sub)
    log(f'  字幕 {len(raw.split())} 字，交給 agy 整理（約 1–3 分鐘）…')
    prompt = PROMPT.format(title=meta['title'], example=example_lines(), raw=raw)
    feedback = ''
    for attempt in (1, 2):
        draft = call_agy(prompt + feedback, model)
        errs, stats = validate(draft, vid)
        if not errs:
            break
        log(f'  ✗ 第 {attempt} 次驗證沒過：' + '；'.join(errs[:6]))
        feedback = '\n\nYOUR PREVIOUS ATTEMPT FAILED THESE CHECKS, fix them and output the full JSON again:\n- ' + '\n- '.join(errs[:20])
    else:
        os.remove(os.path.join(ROOT, 'tools', 'timings', vid + '.json'))
        raise RuntimeError('agy 兩次都沒通過驗證，未寫入')
    path = write_lesson(vid, info, draft)
    log(f"  ✓ {len(draft['lines'])} 句、吻合度 {stats['fidelity']:.0%}、覆蓋率 {stats['coverage']:.0%} → {os.path.relpath(path, ROOT)}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--model', default='Gemini 3.1 Pro (High)')
    ap.add_argument('--keep-going', action='store_true')
    a = ap.parse_args()
    if a.list:
        return list_candidates()
    if not a.ids:
        ap.print_help(); return
    added = 0
    for vid in a.ids:
        try:
            added += add(vid, a.model)
        except Exception as e:
            log(f'  ✗ {e}')
            if not a.keep_going:
                break
        time.sleep(5)  # 別連續打 YouTube
    if added:
        build_data.main()
        bump_sw()
        log(f'\n新增 {added} 課。請人工抽查 content/ 新檔的翻譯，再 commit & push。')


if __name__ == '__main__':
    main()
