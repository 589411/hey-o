"""擴充課程：yt-dlp 抓真字幕（確定性）→ agy 斷句/中譯/選單字（LLM）→ 程式驗證 → 寫 content/<series>/ 並重建 data。

用法：
  python3 tools/add_lesson.py --series heyo --list               # 列出頻道上還沒收錄的影片
  python3 tools/add_lesson.py --series heyo <videoId> […]        # Hey-O：一支影片 = 一課
  python3 tools/add_lesson.py --series bill-johnson <videoId>    # 講道：依 YouTube 章節切成 3–6 分鐘一段，一段 = 一課
    --parts 1-3          只做第 1–3 段（講道很長時先試做）
    --plan               只印出切段計畫，不呼叫 agy
    --jobs 2             同時跑幾個 agy（預設 2）
    --model "Gemini 3.1 Pro (High)"   agy 模型（agy models 可看清單）
    --keep-going         某支失敗時繼續處理下一支

分工原則：影片 ID、字幕、時間軸、切段點一律來自 YouTube／程式（不讓 LLM 碰）；
agy 只負責「把字幕改寫成乾淨句子＋中譯＋單字＋段落標題摘要」。
agy 的輸出要通過 fidelity / coverage 檢查（門檻在 content/series.json）才會寫入。

需要：yt-dlp（brew install yt-dlp，或用環境變數 YTDLP 指向）、agy（Antigravity CLI，已登入）。
"""
import argparse, glob, json, math, os, re, subprocess, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_data  # noqa: E402

YTDLP = os.environ.get('YTDLP', 'yt-dlp')
AGY = os.environ.get('AGY', 'agy')
CACHE = os.path.join(ROOT, 'tools', '.cache')
MIN_LINE = 0.5

# 各系列在程式端的設定（文字類設定在 content/series.json）
SERIES_RULES = {
    'heyo': {
        'channel': 'https://www.youtube.com/@SaddlebackKids/videos',
        'list_re': r'Stories of the Bible\s*$', 'list_skip': r'Church at Home|Available Now|Book Release',
        'author': 'Saddleback', 'segment': False, 'max_bad_lines': 0, 'prompt': 'heyo', 'required': ['ref'],
    },
    'odb': {
        'channel': 'https://www.youtube.com/@ourdailybread/videos',
        'list_re': r'Our Daily Bread Video Devotional', 'list_skip': r'#shorts',
        'author': 'Our Daily Bread', 'segment': False, 'max_bad_lines': 1, 'prompt': 'short', 'required': ['ref', 'summaryZh'],
        'vocab_level': 'intermediate (B1)',
    },
    'billy-graham': {
        'channel': 'https://www.youtube.com/@billygraham/videos',
        'list_re': r'Billy Graham Classic Sermon', 'list_skip': r'#shorts',
        'author': 'Billy Graham', 'segment': True, 'max_bad_lines': 2,
        'min_seg': 150, 'max_seg': 420, 'target_seg': 300,   # 章節很碎（~1.5 分），併成 3–5 分一課
        'level_word': 'INTERMEDIATE', 'speaker': 'evangelist Billy Graham (a classic crusade sermon, slow and plain English)',
        'vocab_level': 'intermediate (B1–B2)',
    },
    'bill-johnson': {
        'channel': 'https://www.youtube.com/channel/UCspy9Ay2Z9VI__qS7Fdbs6Q/videos',
        'list_re': r'Bill Johnson', 'list_skip': r'#shorts|Live Stream|Worship',
        'author': 'Bill Johnson', 'segment': True, 'max_bad_lines': 3,
        'level_word': 'ADVANCED', 'speaker': 'Pastor Bill Johnson (Bethel Church, Redding, California)',
        'vocab_level': 'upper-intermediate (B2–C1)',
        'min_seg': 90, 'max_seg': 420, 'target_seg': 300,
    },
}


def log(*a):
    print(*a, flush=True)


def series_conf(sid):
    for se in build_data.load_series():
        if se['id'] == sid:
            return {**se, **SERIES_RULES[sid]}
    raise SystemExit(f'未知系列：{sid}（content/series.json）')


def content_files(sid):
    return sorted(glob.glob(os.path.join(ROOT, 'content', sid, '*.json')))


# ---------- 1. YouTube（確定性） ----------
def existing_ids(sid):
    return {json.load(open(p))['videoId'] for p in content_files(sid)}


def list_candidates(se):
    out = subprocess.run([YTDLP, '--flat-playlist', '--print', '%(id)s|%(duration)s|%(title)s', se['channel']],
                         capture_output=True, text=True).stdout
    have = existing_ids(se['id'])
    rows = []
    for line in out.splitlines():
        vid, dur, title = (line.split('|', 2) + ['', ''])[:3]
        if re.search(se['list_re'], title) and not re.search(se['list_skip'], title, re.I):
            rows.append((vid, dur, title, vid in have))
    for vid, dur, title, done in rows:
        mins = f'{float(dur) / 60:4.0f}m' if dur not in ('', 'NA', 'None') else '   ?'
        log(f"{'✓' if done else ' '} {vid} {mins}  {title}")
    log(f"\n共 {len(rows)} 支，已收錄 {sum(r[3] for r in rows)} 支。用法：python3 tools/add_lesson.py --series {se['id']} <videoId>")


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
                            '--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', 'en,en-US',
                            '--sub-format', 'json3', '--write-info-json', '-o', os.path.join(CACHE, '%(id)s'),
                            f'https://www.youtube.com/watch?v={vid}'], capture_output=True, text=True)
        us = os.path.join(CACHE, f'{vid}.en-US.json3')
        if not os.path.exists(sub) and os.path.exists(us):
            os.replace(us, sub)
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
    return json.load(open(os.path.join(ROOT, 'tools', 'timings', vid + '.json')))


# ---------- 1b. 切段（確定性；只用於講道） ----------
def plan_segments(info, words, se):
    """回傳 [(startSec, endSec, chapterTitle|None)]。依 YouTube 章節；太短併入前段、太長在最長停頓處切開。"""
    dur = float(info.get('duration') or words[-1][0] / 1000)
    chs = [(float(c['start_time']), float(c['end_time']), c.get('title')) for c in (info.get('chapters') or [])]
    if not chs:
        chs = [(0.0, dur, None)]
    # 太短的併掉：這段或前一段不足 min_seg 就合併（開頭很短的引言會併進下一段）
    merged = []
    for c in chs:
        if merged and (c[1] - c[0] < se['min_seg'] or merged[-1][1] - merged[-1][0] < se['min_seg']):
            p = merged.pop()
            merged.append((p[0], c[1], p[2] if p[1] - p[0] >= c[1] - c[0] else c[2]))
        else:
            merged.append(c)
    # 太長的切開：在目標點 ±45 秒內找最長停頓
    ms = [w[0] / 1000 for w in words]
    out = []
    for a, b, title in merged:
        n = max(1, math.ceil((b - a) / se['target_seg'])) if b - a > se['max_seg'] else 1
        cuts = [a]
        for k in range(1, n):
            target = a + (b - a) * k / n
            best, gap_best = target, -1
            for i in range(1, len(ms)):
                if abs(ms[i] - target) <= 45 and ms[i] - ms[i - 1] > gap_best:
                    gap_best, best = ms[i] - ms[i - 1], ms[i] - 0.3
            cuts.append(best)
        cuts.append(b)
        for k in range(n):
            out.append((round(cuts[k], 2), round(cuts[k + 1], 2), title if n == 1 else (f'{title} ({k + 1}/{n})' if title else None)))
    return out


def window_text(words, a, b):
    ws = [w for t, w in words if a * 1000 <= t < b * 1000]
    return ' '.join(ws)


def snap(words, a, b):
    """把段落邊界貼齊實際字幕字的時間（開頭前 0.3 秒、結尾後 1 秒）。"""
    inside = [t / 1000 for t, _ in words if a * 1000 <= t < b * 1000]
    if not inside:
        return a, b
    return round(max(0, inside[0] - 0.3), 2), round(min(b + 1, inside[-1] + 1.0), 2)


# ---------- 2. agy（LLM） ----------
COMMON_RULES = """Output ONLY one JSON object, no markdown fences, no commentary. Do NOT use any tools or read/write any files.
- If the caption text is in ALL CAPS, write normal sentence case (proper nouns capitalized).
- "zh": natural Traditional Chinese as used in Taiwan. Bible names/places and quoted scripture use 和合本 (Chinese Union Version) wording. Always write God as 「神」 (never 「上帝」) and use 祂 for God/Jesus.
- "vocab": each item is [form, lemma, pos, ipa, zh]
   - form: the word/phrase EXACTLY as it appears in that sentence's "en" (same spelling/inflection, case-sensitive)
   - lemma: dictionary form; pos: one of n. v. adj. adv. prep. conj. phr.; ipa: American IPA in slashes; zh: short Traditional Chinese meaning"""

PROMPT_HEYO = """You are preparing an English listening/speaking lesson for Taiwanese learners from a kids' Bible cartoon.
Below is the RAW YouTube auto-caption text of the video "{title}" (no punctuation, may contain recognition errors).

Your job: rewrite it into clean sentences, translate, and pick vocabulary.
""" + COMMON_RULES + """
Rules:
1. Keep the narrator's ACTUAL words in order. Only add punctuation/capitalization, split into sentences, and fix obvious speech-recognition errors (especially Bible names, e.g. "II" -> "Eve", "Cicora" -> "Sisera"). Do NOT paraphrase, summarize, add, or reorder content.
2. Drop the opening "Hey-O / Stories of the Bible / <title>" intro and meaningless fillers like "hey", "wow", "hmm", "oh", "okay", "yeah", "you", "foreign". Keep everything else.
3. One sentence per line; split very long run-ons at natural clause boundaries. Quoted speech uses double quotes.
4. 0–3 vocab items per sentence for an intermediate learner (skip trivial words and proper names).
5. "titleZh": Chinese lesson title. "ref": the Bible passage in Chinese book names, e.g. "創世記 4".

Output schema (exactly these keys):
{{"titleZh": "...", "ref": "...", "lines": [["English sentence.", "中文翻譯。", [["form","lemma","pos","/ipa/","中文"]]], ...]}}

Example of two lines in the expected style:
{example}

RAW CAPTION TEXT:
{raw}
"""

PROMPT_SERMON = """You are preparing an {level_word} English listening/speaking lesson for Taiwanese Christians from a sermon by {speaker}.
Sermon: "{title}"
This is segment {part} of {parts}{chapter}. Below is the RAW YouTube caption text of this segment only (may lack punctuation and contain recognition errors).

Your job: turn it into clean, learnable sentences, translate, and pick vocabulary.
""" + COMMON_RULES + """
Rules:
1. Keep the speaker's ACTUAL words and order. Add punctuation/capitalization and fix speech-recognition errors (names, scripture words, e.g. "Saidi want" -> "said, \\"I want"). Do NOT paraphrase, summarize, add, or reorder.
2. Remove only disfluencies: "um/uh", false starts, stutters and immediate repeats ("thanks thanks thanks" -> "Thanks."), and crowd reactions. Keep jokes, asides and stories. Drop broadcast announcer intros/outros, music, and ministry ads or phone numbers.
3. The segment may start/end mid-sentence: drop a dangling fragment at the very start or end if it cannot stand alone.
4. One sentence per line, ideally under 25 words; split run-ons at natural clause boundaries. Quoted speech/scripture uses double quotes.
5. Chinese should sound like a Taiwanese church interpreter. Use these terms: presence 同在, anointing 恩膏, breakthrough 突破, the Kingdom 神的國/國度, revival 復興, prophetic 先知性的, prophecy 預言, the Holy Spirit 聖靈, covenant 約, glory 榮耀, testimony 見證, worship 敬拜, intercession 代禱, ministry 服事, faith 信心, grace 恩典, counterfeit 仿冒（不要用「贗品」）, spirit of offense 冒犯的靈, discernment 分辨/辨識, destiny 命定, impart 分賜. Segment titles must state the speaker's actual point, not a literal word-by-word rendering.
6. 0–3 vocab items per sentence for an {vocab_level} learner. Prefer idioms, phrasal verbs, collocations and sermon expressions over single easy words. Skip proper names.
7. Extra keys:
   - "titleZh": Chinese title of the WHOLE sermon{title_hint}
   - "partTitleZh": a short Chinese title for THIS segment (≤ 14 characters)
   - "summaryZh": one Chinese sentence (≤ 40 characters) summarizing this segment's point
   - "ref": the main Bible passage quoted in this segment, Chinese book names (e.g. "馬可福音 4:18-19"), or "" if none

Output schema (exactly these keys):
{{"titleZh": "...", "partTitleZh": "...", "summaryZh": "...", "ref": "...", "lines": [["English sentence.", "中文翻譯。", [["form","lemma","pos","/ipa/","中文"]]], ...]}}

Example of two lines in the expected style:
{example}

RAW CAPTION TEXT:
{raw}
"""


PROMPT_SHORT = """You are preparing an English listening/speaking lesson for Taiwanese Christians from a 2–3 minute devotional video.
Video: "{title}"
Below is the RAW YouTube caption text (may be ALL CAPS, may lack punctuation).

Your job: turn it into clean, learnable sentences, translate, and pick vocabulary.
""" + COMMON_RULES + """
Rules:
1. Keep the speaker's ACTUAL words and order. Fix punctuation/case only. Do NOT paraphrase, summarize, add, or reorder.
2. Drop channel intros/outros (e.g. "Our Daily Bread", music, "subscribe" calls). Keep the story, the Bible verse and the reflection.
3. One sentence per line, ideally under 25 words. Quoted scripture uses double quotes.
4. Chinese should sound natural to Taiwanese Christians; quoted scripture uses 和合本 wording.
5. 0–3 vocab items per sentence for an {vocab_level} learner; prefer useful everyday phrases and collocations. Skip proper names.
6. Extra keys: "titleZh" (Chinese title), "summaryZh" (one Chinese sentence ≤ 40 characters with the takeaway), "ref" (the Bible verse in Chinese book names, e.g. "加拉太書 2:6").

Output schema (exactly these keys):
{{"titleZh": "...", "summaryZh": "...", "ref": "...", "lines": [["English sentence.", "中文翻譯。", [["form","lemma","pos","/ipa/","中文"]]], ...]}}

Example of two lines in the expected style:
{example}

RAW CAPTION TEXT:
{raw}
"""


def example_lines():
    les = json.load(open(content_files('heyo')[0]))
    return json.dumps(les['lines'][1:3], ensure_ascii=False)


def call_agy(prompt, model, timeout_min=10):
    os.makedirs(CACHE, exist_ok=True)
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


def validate(draft, vid, se, clip=None):
    errs = []
    keys = ['titleZh', 'lines'] + (['partTitleZh', 'summaryZh'] if se['segment'] else se.get('required', []))
    for k in keys:
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
    al = build_data.align(lines, vid, clip)
    stats = {'fidelity': al['text_fidelity'], 'coverage': al['caption_coverage']}
    if stats['fidelity'] < se['minFidelity']:
        errs.append(f"英文與字幕吻合度 {stats['fidelity']:.0%} < {se['minFidelity']:.0%}（疑似改寫/編造）")
    if stats['coverage'] < se['minCoverage']:
        errs.append(f"字幕覆蓋率 {stats['coverage']:.0%} < {se['minCoverage']:.0%}（疑似漏段落）")
    bad = [(i, m, t) for i, (m, t) in enumerate(zip(al['matched'], al['total_words'])) if m / max(1, t) < MIN_LINE]
    if len(bad) > se['max_bad_lines']:
        errs += [f'#{i} 對不上字幕（{m}/{t}）：{lines[i][0][:60]}' for i, m, t in bad]
    return errs, stats


def run_agy_validated(prompt, vid, se, model, clip=None, tag=''):
    feedback = ''
    for attempt in (1, 2):
        try:
            draft = call_agy(prompt + feedback, model)
        except Exception as e:
            log(f'  {tag}✗ 第 {attempt} 次 agy 失敗：{e}')
            feedback = '\n\nYOUR PREVIOUS OUTPUT WAS NOT VALID JSON. Output ONLY the JSON object.'
            continue
        errs, stats = validate(draft, vid, se, clip)
        if not errs:
            return draft, stats
        log(f'  {tag}✗ 第 {attempt} 次驗證沒過：' + '；'.join(errs[:6]))
        feedback = '\n\nYOUR PREVIOUS ATTEMPT FAILED THESE CHECKS, fix them and output the full JSON again:\n- ' + '\n- '.join(errs[:20])
    raise RuntimeError(f'{tag}agy 兩次都沒通過驗證，未寫入')


# ---------- 4. 寫入 ----------
def slug(title):
    t = re.split(r'\s*[|(]|\s+-\s+', title)[0].replace("'s ", 's ').replace("’s ", 's ')
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:40].strip('-')


def clean_title(title):
    return re.split(r'\s*[|(]|\s+[-–]\s+(?:Bill Johnson|Best of|Billy Graham)', title)[0].strip()


def next_num(sid):
    nums = [int(os.path.basename(p)[:2]) for p in content_files(sid) if os.path.basename(p)[:2].isdigit()]
    return max(nums, default=0) + 1


ZH_FIXES = [('自已', '自己'), ('上帝', '神')]  # agy 常見錯字／用語統一


def fix_zh(text):
    for a, b in ZH_FIXES:
        text = text.replace(a, b)
    return text


def write_json(path, les, keys):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    les = {k: fix_zh(v) if isinstance(v, str) else v for k, v in les.items()}
    les['lines'] = [[en, fix_zh(zh), [[*v[:4], fix_zh(v[4])] for v in vocab]] for en, zh, vocab in les['lines']]
    with open(path, 'w') as f:
        f.write('{\n')
        for k in keys:
            if k in les:
                f.write(f'  {json.dumps(k)}: {json.dumps(les[k], ensure_ascii=False)},\n')
        f.write('  "lines": [\n' + ',\n'.join('    ' + json.dumps(l, ensure_ascii=False) for l in les['lines']) + '\n  ]\n}\n')


def bump_sw():
    """離線快取與 css/js 的 ?v= 一起升版（避免瀏覽器拿到新 JS + 舊 CSS）。"""
    p = os.path.join(ROOT, 'sw.js')
    s = open(p).read()
    n = int(re.search(r"hey-o-v(\d+)", s).group(1)) + 1
    open(p, 'w').write(re.sub(r"\?v=\d+", f'?v={n}', re.sub(r"hey-o-v\d+", f'hey-o-v{n}', s)))
    p = os.path.join(ROOT, 'index.html')
    html = open(p).read()  # 先讀完再開寫入（open(p,'w') 會先清空檔案）
    open(p, 'w').write(re.sub(r"\?v=\d+", f'?v={n}', html))


def prepare(vid, se):
    if vid in existing_ids(se['id']):
        log('  已收錄，跳過'); return None
    meta = oembed(vid)
    if not meta:
        raise RuntimeError('YouTube 查無此影片（ID 錯誤或已下架）')
    if se['author'] not in meta.get('author_name', ''):
        log(f"  ⚠ 頻道是「{meta.get('author_name')}」，不是預期的 {se['author']}")
    log(f"  影片：{meta['title']}")
    sub, info = fetch_captions(vid)
    if not info.get('playable_in_embed', True):
        raise RuntimeError('這支影片禁止嵌入播放')
    return meta, info, save_timings(vid, sub)


def add_simple(vid, se, model):
    r = prepare(vid, se)
    if not r:
        return 0
    meta, info, words = r
    raw = ' '.join(w for _, w in words)
    log(f'  字幕 {len(raw.split())} 字，交給 agy 整理（約 1–3 分鐘）…')
    tpl = PROMPT_SHORT if se.get('prompt') == 'short' else PROMPT_HEYO
    prompt = tpl.format(title=meta['title'], example=example_lines(), raw=raw, vocab_level=se.get('vocab_level', ''))
    draft, stats = run_agy_validated(prompt, vid, se, model)
    les = {'id': slug(info['title']), 'videoId': vid, 'title': clean_title(info['title']), 'titleZh': draft['titleZh'],
           'ref': draft.get('ref', ''), 'duration': int(info.get('duration') or 0), 'lines': draft['lines']}
    if draft.get('summaryZh'):
        les['summaryZh'] = draft['summaryZh']
    if any(json.load(open(p))['id'] == les['id'] for p in content_files(se['id'])):
        les['id'] += '-' + vid[:4].lower()
    path = os.path.join(ROOT, 'content', se['id'], f'{next_num(se["id"]):02d}-{les["id"]}.json')
    write_json(path, les, ['id', 'videoId', 'title', 'titleZh', 'summaryZh', 'ref', 'duration'])
    log(f"  ✓ {len(draft['lines'])} 句、吻合度 {stats['fidelity']:.0%}、覆蓋率 {stats['coverage']:.0%} → {os.path.relpath(path, ROOT)}")
    return 1


def parse_parts(spec, n):
    if not spec:
        return list(range(1, n + 1))
    out = set()
    for tok in spec.split(','):
        a, _, b = tok.partition('-')
        out.update(range(int(a), int(b or a) + 1))
    return [k for k in sorted(out) if 1 <= k <= n]


def add_sermon(vid, se, model, parts_spec=None, plan_only=False, jobs=2):
    r = prepare(vid, se)
    if not r:
        return 0
    meta, info, words = r
    segs = plan_segments(info, words, se)
    title = clean_title(info['title'])
    log(f'  切成 {len(segs)} 段：')
    for k, (a, b, ch) in enumerate(segs, 1):
        log(f'   {k:2d}. {int(a) // 60:02d}:{int(a) % 60:02d}–{int(b) // 60:02d}:{int(b) % 60:02d}（{(b - a) / 60:.1f} 分，{len(window_text(words, a, b).split())} 字）{ch or ""}')
    if plan_only:
        return 0
    todo = parse_parts(parts_spec, len(segs))
    num, base = next_num(se['id']), slug(info['title'])
    title_zh = {}

    def one(k):
        a, b, ch = segs[k - 1]
        clip = snap(words, a, b)
        raw = window_text(words, a, b)
        tag = f'[{k}/{len(segs)}] '
        log(f'  {tag}{len(raw.split())} 字交給 agy…')
        hint = f' — use exactly: {title_zh["v"]}' if 'v' in title_zh else ''
        prompt = PROMPT_SERMON.format(title=title, part=k, parts=len(segs), chapter=f' (chapter: "{ch}")' if ch else '',
                                      title_hint=hint, example=example_lines(), raw=raw, level_word=se['level_word'],
                                      speaker=se['speaker'], vocab_level=se['vocab_level'])
        draft, stats = run_agy_validated(prompt, vid, se, model, clip, tag)
        title_zh.setdefault('v', draft['titleZh'])
        les = {'id': f'{base}-p{k}', 'videoId': vid, 'title': title, 'titleZh': title_zh['v'],
               'part': k, 'parts': len(segs), 'partTitle': ch, 'partTitleZh': draft['partTitleZh'],
               'summaryZh': draft['summaryZh'], 'ref': draft.get('ref') or '',
               'clipStart': clip[0], 'clipEnd': clip[1], 'lines': draft['lines']}
        path = os.path.join(ROOT, 'content', se['id'], f'{num:02d}-{base}-p{k:02d}.json')
        write_json(path, les, ['id', 'videoId', 'title', 'titleZh', 'part', 'parts', 'partTitle', 'partTitleZh',
                               'summaryZh', 'ref', 'clipStart', 'clipEnd'])
        log(f"  {tag}✓ {len(draft['lines'])} 句、吻合度 {stats['fidelity']:.0%}、覆蓋率 {stats['coverage']:.0%}「{draft['partTitleZh']}」")
        return 1

    # 第一段先跑，定下講道中文標題，其餘並行
    done = 0
    try:
        done += one(todo[0])
    except Exception as e:
        log(f'  ✗ {e}')
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for fut in [ex.submit(one, k) for k in todo[1:]]:
            try:
                done += fut.result()
            except Exception as e:
                log(f'  ✗ {e}')
    if done < len(todo):
        log(f'  ⚠ {len(todo) - done} 段失敗，可用 --parts 重跑那幾段（先刪掉 tools/timings 不用，已存在會沿用）')
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--series', default='heyo')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--parts')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--model', default='Gemini 3.1 Pro (High)')
    ap.add_argument('--keep-going', action='store_true')
    a = ap.parse_args()
    se = series_conf(a.series)
    if a.list:
        return list_candidates(se)
    if not a.ids:
        ap.print_help(); return
    added = 0
    for vid in a.ids:
        log(f'▸ {vid}')
        try:
            if se['segment']:
                added += add_sermon(vid, se, a.model, a.parts, a.plan, a.jobs)
            else:
                added += add_simple(vid, se, a.model)
        except Exception as e:
            log(f'  ✗ {e}')
            if not a.keep_going:
                break
        time.sleep(5)  # 別連續打 YouTube
    if added:
        build_data.main()
        bump_sw()
        log(f'\n新增 {added} 課。請人工抽查 content/{se["id"]}/ 新檔的翻譯，再 commit & push。')


if __name__ == '__main__':
    main()
