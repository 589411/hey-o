/* Hey-O! 英聽口說 — 單頁 App（hash 路由，無框架）
 * 路由：#/            課程列表
 *       #/l/<id>[/mode] 課程（mode = listen | shadow | dictation | vocab）
 *       #/words       生字本
 * 進度存 localStorage（只在這台裝置）。
 */
(() => {
  'use strict';

  // ---------- utils ----------
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = sec => { sec = Math.max(0, Math.floor(sec)); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`; };
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const ICON = {
    play: '<svg viewBox="0 0 24 24"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    prev: '<svg viewBox="0 0 24 24"><path d="M6 5h2v14H6zM19 6.2v11.6a.8.8 0 0 1-1.25.66L9.5 12.66a.8.8 0 0 1 0-1.32l8.25-5.8A.8.8 0 0 1 19 6.2z"/></svg>',
    next: '<svg viewBox="0 0 24 24"><path d="M16 5h2v14h-2zM5 6.2v11.6a.8.8 0 0 0 1.25.66l8.25-5.8a.8.8 0 0 0 0-1.32L6.25 5.54A.8.8 0 0 0 5 6.2z"/></svg>',
    loop: '<svg viewBox="0 0 24 24"><path d="M7 7h10v3l4-4-4-4v3H5v6h2zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2z"/></svg>',
    mic: '<svg viewBox="0 0 24 24"><path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-6a3.5 3.5 0 1 0-7 0v6A3.5 3.5 0 0 0 12 15zm6-3.5a6 6 0 0 1-12 0H4a8 8 0 0 0 7 7.93V22h2v-2.57a8 8 0 0 0 7-7.93z"/></svg>',
    ear: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05A4.47 4.47 0 0 0 16.5 12zM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06a9 9 0 0 0 0-17.54z"/></svg>',
    turtle: '🐢',
    back: '<svg viewBox="0 0 24 24"><path d="M15.4 5.4 14 4l-8 8 8 8 1.4-1.4L8.8 12z"/></svg>',
    star: '<svg viewBox="0 0 24 24"><path d="M12 17.3 18.2 21l-1.6-7L22 9.2l-7.2-.6L12 2 9.2 8.6 2 9.2 7.4 14l-1.6 7z"/></svg>',
    starO: '<svg viewBox="0 0 24 24"><path d="m22 9.2-7.2-.6L12 2 9.2 8.6 2 9.2 7.4 14l-1.6 7 6.2-3.7 6.2 3.7-1.6-7L22 9.2zM12 15.4l-3.8 2.3 1-4.3-3.3-2.9 4.4-.4L12 6.1l1.7 4 4.4.4-3.3 2.9 1 4.3-3.8-2.3z"/></svg>'
  };

  // ---------- storage ----------
  const KEY = 'heyo.v1';
  const store = (() => {
    let s;
    try { s = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { s = {}; }
    s.lessons ||= {}; s.words ||= {}; s.days ||= {}; s.prefs ||= { hideZh: false, hideEn: false, follow: true, rate: 1 };
    return s;
  })();
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(store)); } catch { /* 私密模式等情況：只是不存 */ } };
  const lp = id => (store.lessons[id] ||= { shadow: {}, dict: {}, last: 0 });
  const bumpToday = () => { store.days[today()] = (store.days[today()] || 0) + 1; save(); renderHeader(); };
  const streak = () => {
    let n = 0; const d = new Date();
    if (!store.days[today()]) d.setDate(d.getDate() - 1); // 今天還沒練不算斷
    for (;;) {
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      if (!store.days[k]) break; n++; d.setDate(d.getDate() - 1);
    }
    return n;
  };
  const lessonProgress = L => {
    const p = store.lessons[L.id]; if (!p) return 0;
    const done = L.lines.filter((_, i) => (p.shadow[i] || 0) >= 70 || (p.dict[i] || 0) >= 70).length;
    return done / L.lines.length;
  };

  // ---------- data ----------
  let DATA = null;
  const lessonById = id => DATA.lessons.find(l => l.id === id);

  // ---------- header / toast ----------
  function renderHeader() {
    const n = streak();
    $('#streak').textContent = n ? `🔥 ${n} 天` : '';
    const c = Object.keys(store.words).length;
    $('#wordCount').textContent = c || '';
  }
  let toastTimer;
  function toast(msg, ms = 2400) {
    const t = $('#toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), ms);
  }

  // ---------- speech (TTS) ----------
  function speak(text, rate = 0.9) {
    if (!('speechSynthesis' in window)) return toast('這個瀏覽器不支援發音');
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text); u.lang = 'en-US'; u.rate = rate;
    const v = speechSynthesis.getVoices().find(v => /en[-_]US/i.test(v.lang) && /Samantha|Google|Aria|Jenny/i.test(v.name))
      || speechSynthesis.getVoices().find(v => /en[-_]US/i.test(v.lang));
    if (v) u.voice = v;
    speechSynthesis.speak(u);
  }

  // ---------- word compare（跟讀/聽寫共用） ----------
  const ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
  const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
  function numWords(n) {
    if (n < 20) return ONES[n];
    if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? ' ' + ONES[n % 10] : '');
    if (n < 1000) return ONES[Math.floor(n / 100)] + ' hundred' + (n % 100 ? ' ' + numWords(n % 100) : '');
    if (n < 1e6) return numWords(Math.floor(n / 1000)) + ' thousand' + (n % 1000 ? ' ' + numWords(n % 1000) : '');
    return String(n);
  }
  const CONTRACT = { "i'm": 'i am', "i'll": 'i will', "won't": 'will not', "don't": 'do not', "didn't": 'did not', "can't": 'can not', "cannot": 'can not', "wouldn't": 'would not', "weren't": 'were not', "couldn't": 'could not', "hasn't": 'has not', "that's": 'that is', "let's": 'let us', "it's": 'it is', "you'll": 'you will' };
  function normTokens(text) {
    const out = [];
    text.toLowerCase().replace(/[’‘]/g, "'").replace(/(\d),(\d)/g, '$1$2').split(/[\s\-—–]+/).forEach(raw => {
      let w = raw.replace(/[^a-z0-9']/g, '').replace(/^'+|'+$/g, '');
      if (!w) return;
      if (/^\d+$/.test(w)) return out.push(...numWords(+w).split(' '));
      if (CONTRACT[w]) return out.push(...CONTRACT[w].split(' '));
      w = w.replace(/'s$/, '');
      out.push(w);
    });
    return out;
  }
  /** 回傳 target 每個「顯示字」是否被說/寫對，與分數 */
  function compare(target, said) {
    const disp = target.split(/\s+/).filter(Boolean);
    // 每個顯示字展開成 token，記錄 token→顯示字索引
    const tTok = [], owner = [];
    disp.forEach((d, i) => normTokens(d).forEach(t => { tTok.push(t); owner.push(i); }));
    const sTok = normTokens(said);
    // LCS
    const n = tTok.length, m = sTok.length;
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      dp[i][j] = tTok[i] === sTok[j] || close(tTok[i], sTok[j]) ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const hit = new Array(n).fill(false);
    for (let i = 0, j = 0; i < n && j < m;) {
      if (tTok[i] === sTok[j] || close(tTok[i], sTok[j])) { hit[i] = true; i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) i++; else j++;
    }
    const wordOk = disp.map(() => ({ tot: 0, ok: 0 }));
    tTok.forEach((_, k) => { wordOk[owner[k]].tot++; if (hit[k]) wordOk[owner[k]].ok++; });
    const status = wordOk.map(w => w.tot === 0 ? 'ok' : (w.ok / w.tot >= 0.5 ? 'ok' : 'miss'));
    const score = n ? Math.round(100 * hit.filter(Boolean).length / n) : 0;
    return { disp, status, score };
  }
  // 容忍小拼字差（聽寫）與語音辨識常見同音
  function close(a, b) {
    if (a.length < 4 || b.length < 4) return false;
    if (Math.abs(a.length - b.length) > 1) return false;
    let diff = 0;
    for (let i = 0, j = 0; i < a.length || j < b.length;) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++diff > 1) return false;
      if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++; }
    }
    return true;
  }
  const wordsHtml = (cmp, masked = false) =>
    `<div class="target${masked ? ' masked' : ''}">${cmp.disp.map((w, i) => `<span class="w ${cmp.status ? cmp.status[i] || '' : ''}">${esc(w)}</span>`).join(' ')}</div>`;

  // ---------- vocab highlight ----------
  function highlight(line, li) {
    let html = esc(line.en);
    // 長片語先做，避免被短字切掉
    [...line.vocab].map((v, vi) => ({ v, vi })).sort((a, b) => b.v.form.length - a.v.form.length).forEach(({ v, vi }) => {
      const re = new RegExp(`(^|[^A-Za-z'>])(${v.form.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})(?![A-Za-z])`);
      html = html.replace(re, (_, pre, w) => `${pre}<span class="vocab${store.words[v.lemma] ? ' saved' : ''}" tabindex="0" data-li="${li}" data-vi="${vi}">${w}</span>`);
    });
    return html;
  }

  // ---------- YouTube player ----------
  const YTReady = new Promise(res => {
    if (window.YT && window.YT.Player) return res();
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev && prev(); res(); };
  });
  const P = {
    yt: null, ready: false, lesson: null, stopAt: null, loopIdx: null, cur: -1, timer: null, onTick: null,
    async mount(lesson) {
      this.destroy();
      this.lesson = lesson;
      await YTReady;
      if (this.lesson !== lesson) return;
      this.yt = new YT.Player('player', {
        videoId: lesson.videoId,
        playerVars: { playsinline: 1, rel: 0, modestbranding: 1, cc_load_policy: 0, iv_load_policy: 3,
          ...(lesson.clipStart != null ? { start: Math.floor(lesson.clipStart), end: Math.ceil(lesson.clipEnd) } : {}) },
        events: {
          onReady: () => { this.ready = true; this.setRate(store.prefs.rate); },
          onStateChange: e => { renderPlayBtn(); if (e.data === 1) this.startTimer(); }
        }
      });
    },
    destroy() {
      clearInterval(this.timer); this.timer = null;
      try { this.yt && this.yt.destroy(); } catch { }
      this.yt = null; this.ready = false; this.stopAt = null; this.loopIdx = null; this.cur = -1;
    },
    time() { return this.ready ? this.yt.getCurrentTime() : 0; },
    playing() { return this.ready && this.yt.getPlayerState() === 1; },
    setRate(r) { store.prefs.rate = r; save(); if (this.ready) this.yt.setPlaybackRate(r); },
    toggle() {
      if (!this.ready) return toast('影片載入中…');
      if (this.playing()) { this.yt.pauseVideo(); return; }
      this.stopAt = null;
      // 講道片段：不在本段範圍內就從本段第一句開始
      const L = this.lesson, t = this.time();
      if (L.clipStart != null && (t < L.clipStart - 1 || t >= L.clipEnd - 0.5)) this.yt.seekTo(L.lines[0].t, true);
      this.yt.playVideo(); this.nudge();
    },
    /** 播單句，句尾自動停 */
    playLine(i, { rate } = {}) {
      if (!this.ready) return toast('影片載入中…');
      const L = this.lesson.lines[i]; if (!L) return;
      if (rate) this.yt.setPlaybackRate(rate); else this.yt.setPlaybackRate(store.prefs.rate);
      this.stopAt = { i, end: L.end, restoreRate: !!rate };
      this.yt.seekTo(L.t, true); this.yt.playVideo(); this.nudge();
    },
    /** 從某句開始連續播放 */
    playFrom(i) {
      if (!this.ready) return toast('影片載入中…');
      this.stopAt = null; this.yt.setPlaybackRate(store.prefs.rate);
      this.yt.seekTo(this.lesson.lines[i].t, true); this.yt.playVideo(); this.nudge();
    },
    // iOS 有時第一次要使用者親手點影片
    nudge() { setTimeout(() => { if (this.ready && this.yt.getPlayerState() !== 1 && this.yt.getPlayerState() !== 3) toast('若沒有聲音，請先點一下影片畫面開始播放', 3500); }, 1800); },
    lineAt(t) {
      const ls = this.lesson.lines; let k = -1;
      for (let i = 0; i < ls.length; i++) { if (ls[i].t <= t + 0.05) k = i; else break; }
      if (k === ls.length - 1 && t > ls[k].end + 2) return -1;  // 已超出本段
      return k;
    },
    startTimer() {
      if (this.timer) return;
      this.timer = setInterval(() => {
        if (!this.ready) return;
        const t = this.time();
        if (this.stopAt && t >= this.stopAt.end) {
          const { i, restoreRate } = this.stopAt;
          if (this.loopIdx === i) { this.yt.seekTo(this.lesson.lines[i].t, true); }
          else { this.yt.pauseVideo(); this.stopAt = null; if (restoreRate) this.yt.setPlaybackRate(store.prefs.rate); this.onLineEnd && this.onLineEnd(i); }
        } else if (this.loopIdx != null && !this.stopAt) {
          const L = this.lesson.lines[this.loopIdx];
          if (t >= L.end || t < L.t - 1) this.yt.seekTo(L.t, true);
        }
        if (this.lesson.clipEnd != null && !this.stopAt && this.loopIdx == null && t >= this.lesson.clipEnd) this.yt.pauseVideo();
        const k = this.lineAt(t);
        if (k !== this.cur) { this.cur = k; this.onTick && this.onTick(k); }
        if (!this.playing() && !this.stopAt) { clearInterval(this.timer); this.timer = null; }
      }, 120);
    }
  };

  // ---------- speech recognition ----------
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null;      // 目前的辨識 session：{ r, stop(), abort() }
  const SILENCE_MS = 1500;   // 講完後靜默多久就自動評分
  const NO_SPEECH_MS = 8000; // 一直沒出聲就結束
  const WATCHDOG_MS = 2000;  // stop() 後瀏覽器遲遲不回 onend（iOS 偶發）就強制收尾
  /** 語音辨識，附保險：靜默自動結束、最長時限、強制收尾。onEnd 保證只會被呼叫一次。 */
  function listen({ onResult, onEnd, onError, maxMs = 20000 }) {
    if (rec) { rec.stop(); return; }
    const r = new SR(); r.lang = 'en-US'; r.interimResults = true; r.continuous = false; r.maxAlternatives = 1;
    let text = '', done = false, stopping = false;
    const timers = {};
    const clear = () => Object.values(timers).forEach(clearTimeout);
    const finish = () => {
      if (done) return; done = true; clear();
      if (rec && rec.r === r) rec = null;
      onEnd(text);
    };
    const stop = () => {
      if (done || stopping) return; stopping = true;
      try { r.stop(); } catch { }
      timers.watch = setTimeout(() => { try { r.abort(); } catch { } finish(); }, WATCHDOG_MS);
    };
    const abort = () => { onError = null; try { r.abort(); } catch { } text = ''; finish(); };
    rec = { r, stop, abort };
    r.onresult = e => {
      if (done) return;  // 已收尾（watchdog/abort）後才到的結果不要蓋掉分數
      const parts = [];
      for (let i = 0; i < e.results.length; i++) {
        const t = e.results[i][0].transcript.trim();
        // iOS 有時把「越來越長的同一句」放在不同 index，只留最長的那個
        if (parts.length && t.startsWith(parts[parts.length - 1])) parts[parts.length - 1] = t; else if (t) parts.push(t);
      }
      text = parts.join(' ').trim();
      onResult && onResult(text);
      clearTimeout(timers.noSpeech); clearTimeout(timers.silence);
      timers.silence = setTimeout(stop, SILENCE_MS);
    };
    r.onerror = e => { if (e.error !== 'aborted' && onError) onError(e.error); stop(); };
    r.onend = finish;
    timers.noSpeech = setTimeout(stop, NO_SPEECH_MS);
    timers.max = setTimeout(stop, maxMs);
    try { r.start(); } catch (e) { onError && onError(String(e.message || e)); finish(); }
  }
  // 不支援辨識（例如 Firefox）時：錄音後自己聽
  let mediaRec = null, lastBlobUrl = null;
  async function recordSelf(btn, resultEl) {
    if (mediaRec) { mediaRec.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = []; mediaRec = new MediaRecorder(stream);
      mediaRec.ondataavailable = e => chunks.push(e.data);
      mediaRec.onstop = () => {
        stream.getTracks().forEach(t => t.stop()); mediaRec = null;
        btn.classList.remove('recording'); btn.innerHTML = `${ICON.mic} 再錄一次`;
        if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
        lastBlobUrl = URL.createObjectURL(new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' }));
        resultEl.hidden = false;
        resultEl.innerHTML = `<div class="heard">這個瀏覽器不支援自動評分，聽聽自己的錄音和原音比較：</div><audio controls src="${lastBlobUrl}" style="width:100%;margin-top:8px"></audio>`;
      };
      mediaRec.start(); btn.classList.add('recording'); btn.innerHTML = `${ICON.mic} 錄音中…點一下停止`;
    } catch { toast('無法使用麥克風，請檢查權限'); }
  }

  // ---------- sheet (單字卡) ----------
  function openWord(v, line, lessonId, li) {
    const saved = !!store.words[v.lemma];
    $('#sheet').innerHTML = `
      <div class="grab"></div>
      <div class="w">${esc(v.form)}${v.lemma !== v.form ? ` <span style="font-size:16px;color:var(--ink-3);font-weight:700">← ${esc(v.lemma)}</span>` : ''}</div>
      <div class="ipa">${esc(v.ipa || '')}</div>
      <div class="m"><span class="pos">${esc(v.pos)}</span>${esc(v.zh)}</div>
      ${line ? `<div class="ex">${esc(line.en)}<br><span style="font-size:13px">${esc(line.zh)}</span></div>` : ''}
      <div class="row">
        <button class="btn" data-act="say">${ICON.ear} 發音</button>
        <button class="btn ${saved ? 'teal' : 'primary'}" data-act="save">${saved ? ICON.star + ' 已收藏' : ICON.starO + ' 加入生字本'}</button>
      </div>`;
    $('#sheet').hidden = false; $('#sheetBackdrop').hidden = false;
    speak(v.lemma);
    $('#sheet').onclick = e => {
      const b = e.target.closest('[data-act]'); if (!b) return;
      if (b.dataset.act === 'say') speak(v.lemma);
      if (b.dataset.act === 'save') { toggleWord(v, lessonId, li); openWordRefresh(v, line, lessonId, li); }
    };
  }
  const openWordRefresh = (v, line, lessonId, li) => { openWord(v, line, lessonId, li); speechSynthesis.cancel(); refreshVocabMarks(); };
  function closeSheet() { $('#sheet').hidden = true; $('#sheetBackdrop').hidden = true; }
  $('#sheetBackdrop').onclick = closeSheet;
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });

  function toggleWord(v, lessonId, li) {
    if (store.words[v.lemma]) { delete store.words[v.lemma]; toast('已從生字本移除'); }
    else { store.words[v.lemma] = { ...v, lesson: lessonId, li, added: Date.now() }; toast('已加入生字本 ⭐'); }
    save(); renderHeader();
  }
  function refreshVocabMarks() {
    $$('.vocab').forEach(el => {
      const L = currentLesson(); if (!L) return;
      const v = L.lines[el.dataset.li].vocab[el.dataset.vi];
      el.classList.toggle('saved', !!store.words[v.lemma]);
    });
  }

  // ---------- views ----------
  const app = $('#app');
  let view = { name: '', lessonId: null, mode: 'listen' };
  const currentLesson = () => view.lessonId && lessonById(view.lessonId);

  // ---- 系列與課程顯示名稱 ----
  const seriesOf = L => DATA.series.find(se => se.id === L.series) || DATA.series[0];
  const seriesLessons = sid => DATA.lessons.filter(l => l.series === sid);
  const lessonNo = L => seriesLessons(L.series).indexOf(L) + 1;
  const isSermon = L => L.part != null;
  /** 卡片/標題用：{ main 主標, sub 副標, badge 角標 } */
  function names(L) {
    if (isSermon(L) && L.parts === 1) return {  // 官方短片：整支就一段
      main: L.titleZh, sub: L.partTitleZh, badge: `第 ${lessonNo(L)} 課`, head: L.titleZh, headSub: L.title
    };
    if (isSermon(L)) return {
      main: L.partTitleZh, sub: `${L.titleZh}・第 ${L.part}/${L.parts} 段`, badge: `第 ${lessonNo(L)} 課`,
      head: `${L.titleZh}・第 ${L.part}/${L.parts} 段`, headSub: `${L.title}${L.partTitle ? '・' + L.partTitle : ''}`
    };
    return { main: L.titleZh, sub: L.title, badge: `第 ${lessonNo(L)} 課`, head: `第 ${lessonNo(L)} 課・${L.titleZh}`, headSub: L.title };
  }
  const curSeries = () => DATA.series.find(se => se.id === store.prefs.series) || DATA.series[0];

  function renderHome() {
    P.destroy();
    const last = store.last && lessonById(store.last.id);
    const se = curSeries();
    const list = seriesLessons(se.id);
    const totalLines = list.reduce((a, l) => a + l.lines.length, 0);
    app.innerHTML = `
      <section class="hero">
        <h1>用 YouTube<br><em>練英聽、開口說</em></h1>
        <p>真實影片＋逐句對齊的字幕：一句一句聽懂、跟讀、寫下來。</p>
      </section>
      ${last ? `
      <a class="continue" href="#/l/${last.id}/${store.last.mode || 'listen'}">
        <img src="https://i.ytimg.com/vi/${last.videoId}/mqdefault.jpg" alt="">
        <div><div class="k">繼續上次・${esc(seriesOf(last).title)}</div><div class="t">${esc(names(last).main)}</div><div class="s">第 ${(store.last.idx || 0) + 1} 句・${Math.round(lessonProgress(last) * 100)}% 完成</div></div>
        <span class="go">→</span>
      </a>` : ''}
      <div class="series" role="tablist" aria-label="系列">
        ${DATA.series.map(x => `<a class="series-card" role="tab" href="#/s/${x.id}" aria-selected="${x.id === se.id}">
          <span class="lvl lvl-t${x.tier || 1}">${esc(x.level)}</span>
          <b>${esc(x.title)}</b><small>${x.count} 課</small>
        </a>`).join('')}
      </div>
      <p class="series-blurb">${esc(se.blurb)}</p>
      <div class="steps" aria-label="學習四步驟">
        <div class="step"><b>🎧</b><span>1 盲聽</span><small>先蓋住字幕<br>抓大意</small></div>
        <div class="step"><b>📖</b><span>2 對照</span><small>看中英文<br>查生字</small></div>
        <div class="step"><b>🗣️</b><span>3 跟讀</span><small>一句一句<br>說到 80 分</small></div>
        <div class="step"><b>✍️</b><span>4 聽寫</span><small>聽到就能<br>寫得出來</small></div>
      </div>
      <div class="section-title"><h2>${esc(se.title)}</h2><span>${list.length} 課・${totalLines} 句${se.order === 'bible' ? '・依聖經順序' : ''}</span></div>
      ${list.length ? `<div class="grid">
        ${list.map(l => {
          const pr = lessonProgress(l), n = names(l);
          return `<a class="card" href="#/l/${l.id}">
            <div class="thumb">
              <img loading="lazy" src="https://i.ytimg.com/vi/${l.videoId}/mqdefault.jpg" alt="">
              <span class="num">${n.badge}</span>
              ${pr >= 0.999 ? '<span class="done-badge">✓ 完成</span>' : ''}
              <span class="dur">${fmt(l.duration)}</span>
            </div>
            <div class="body">
              <div class="zh">${esc(n.main)}</div>
              <div class="en">${esc(n.sub)}</div>
              ${l.summaryZh ? `<div class="sum">${esc(l.summaryZh)}</div>` : ''}
              <div class="meta">${l.ref ? `<span>📖 ${esc(l.ref)}</span>` : ''}<span>${l.lines.length} 句</span><span>${l.lines.reduce((a, x) => a + x.vocab.length, 0)} 字</span></div>
              <div class="bar"><i style="width:${Math.round(pr * 100)}%"></i></div>
            </div>
          </a>`;
        }).join('')}
      </div>` : '<div class="empty"><b>🛠️</b>這個系列的課程準備中</div>'}
      <p class="footer-note">影片來源：<a href="${esc(se.creditUrl)}" target="_blank" rel="noopener">${esc(se.credit)}</a>《${esc(se.titleEn)}》，本站僅嵌入 YouTube 播放。<br>逐字稿由 YouTube 字幕校對而成，中文翻譯與單字為自編學習用。<br>學習進度只存在這台裝置。</p>`;
  }

  function renderWords() {
    P.destroy();
    const words = Object.values(store.words).sort((a, b) => b.added - a.added);
    app.innerHTML = `
      <a href="#/" class="back" style="display:inline-flex;align-items:center;gap:4px;color:var(--ink-2);text-decoration:none;font-weight:700;font-size:14px">${ICON.back} 課程</a>
      <section class="hero"><h1>生字本</h1><p>${words.length ? `共 ${words.length} 個字。點卡片翻面，記不得就再看一次。` : ''}</p></section>
      ${words.length ? `
        <div class="chips"><button class="chip" aria-pressed="true" data-wm="flash">閃卡複習</button><button class="chip" data-wm="list">清單</button></div>
        <div id="wbody"></div>` : `
        <div class="empty"><b>⭐</b>還沒有收藏的單字<br><small>上課時點<span class="vocab" style="pointer-events:none">黃色底線</span>的字，就能加進來。</small></div>`}`;
    if (!words.length) return;
    let mode = 'flash', idx = 0, flipped = false;
    const order = words.slice().sort(() => Math.random() - 0.5);
    const body = $('#wbody');
    const draw = () => {
      $$('[data-wm]').forEach(b => b.setAttribute('aria-pressed', b.dataset.wm === mode));
      if (mode === 'list') { body.innerHTML = vocabListHtml(words, true); return; }
      const w = order[idx % order.length];
      const L = lessonById(w.lesson); const line = L && L.lines[w.li];
      body.innerHTML = `
        <div class="p-count" style="margin:6px 0">${(idx % order.length) + 1} / ${order.length}</div>
        <div class="flash"><div class="flash-card" id="fc">
          ${flipped
            ? `<div class="big" style="font-size:26px">${esc(w.zh)}</div><div style="color:var(--teal);font-weight:800;margin-top:4px">${esc(w.pos)}・${esc(w.lemma)} ${esc(w.ipa || '')}</div>${line ? `<div class="ex">${esc(line.en)}</div>` : ''}`
            : `<div class="big">${esc(w.lemma)}</div><div class="hint">想想中文意思，再點一下翻面</div>`}
        </div></div>
        <div class="actions">
          <button class="btn" data-f="say">${ICON.ear} 發音</button>
          <button class="btn primary" data-f="next">下一張 →</button>
        </div>`;
      $('#fc').onclick = () => { flipped = !flipped; draw(); };
      if (!flipped) speak(w.lemma);
    };
    app.onclick = e => {
      const wm = e.target.closest('[data-wm]'); if (wm) { mode = wm.dataset.wm; draw(); return; }
      const f = e.target.closest('[data-f]');
      if (f && f.dataset.f === 'say') speak(order[idx % order.length].lemma);
      if (f && f.dataset.f === 'next') { idx++; flipped = false; draw(); }
      handleVocabListClick(e);
    };
    draw();
  }

  function vocabListHtml(items, showLesson) {
    return `<div class="vlist">${items.map(v => {
      const L = lessonById(v.lesson); const on = !!store.words[v.lemma];
      return `<div class="vitem" data-lemma="${esc(v.lemma)}" data-lesson="${esc(v.lesson)}" data-li="${v.li}">
        <div><span class="w">${esc(v.lemma)}</span><span class="ipa">${esc(v.ipa || '')}</span></div>
        <div class="btns">
          <button class="round" data-v="say" aria-label="發音">${ICON.ear}</button>
          <button class="round ${on ? 'on' : ''}" data-v="star" aria-label="收藏">${on ? ICON.star : ICON.starO}</button>
        </div>
        <div class="m"><span class="pos">${esc(v.pos)}</span>${esc(v.zh)}</div>
        ${L ? `<div class="src" data-v="go">${showLesson ? `${esc(names(L).main)}・` : ''}「${esc(L.lines[v.li].en.slice(0, 60))}${L.lines[v.li].en.length > 60 ? '…' : ''}」</div>` : ''}
      </div>`;
    }).join('')}</div>`;
  }
  function handleVocabListClick(e) {
    const b = e.target.closest('[data-v]'); if (!b) return;
    const item = b.closest('.vitem');
    const L = lessonById(item.dataset.lesson); const li = +item.dataset.li;
    const v = (L && L.lines[li].vocab.find(x => x.lemma === item.dataset.lemma)) || store.words[item.dataset.lemma];
    if (b.dataset.v === 'say') speak(v.lemma);
    if (b.dataset.v === 'star') {
      toggleWord(v, L.id, li);
      const on = !!store.words[v.lemma]; b.classList.toggle('on', on); b.innerHTML = on ? ICON.star : ICON.starO;
    }
    if (b.dataset.v === 'go') {
      if (view.name === 'lesson' && view.lessonId === L.id) { setMode('listen'); setTimeout(() => P.playFrom(li), 50); }
      else location.hash = `#/l/${L.id}/listen`;
    }
  }

  // ---- Lesson ----
  const MODES = [
    { id: 'listen', label: '聽讀', sub: '跟著影片', tip: '點任一句從那裡播放。先開「蓋住英文」盲聽一遍，再打開對照。黃色底線的字可以點。' },
    { id: 'shadow', label: '跟讀', sub: '口說評分', tip: '先聽原音，再按「換我說」模仿。綠色＝說對，紅色＝再練。80 分以上就過關！' },
    { id: 'dictation', label: '聽寫', sub: '聽力檢測', tip: '只聽不看，把聽到的句子打出來。拼錯一兩個字母也算對，標點不用管。' },
    { id: 'vocab', label: '單字', sub: '本課生字', tip: '點 ⭐ 收進生字本，之後可以用閃卡複習。點例句可跳回影片那一句。' }
  ];

  function renderLesson(id, mode) {
    const L = lessonById(id);
    if (!L) { location.hash = '#/'; return; }
    const sameLesson = view.name === 'lesson' && view.lessonId === id && $('#player');
    view = { name: 'lesson', lessonId: id, mode };
    const p = lp(id);
    store.last = { id, mode, idx: p.last || 0 }; save();
    if (!sameLesson) {
      const n = names(L);
      app.innerHTML = `
        <div class="lesson">
          <div class="left">
            <a href="#/s/${L.series}" class="back">${ICON.back} ${esc(seriesOf(L).title)}</a>
            <div class="video-sticky"><div class="video-wrap"><div id="player"></div></div></div>
            <div class="lesson-head">
              <h1>${esc(n.head)}</h1>
              ${isSermon(L) && L.parts > 1 ? `<p class="part-title">${esc(L.partTitleZh)}</p>` : ''}
              <p>${esc(n.headSub)}${L.ref ? `・📖 ${esc(L.ref)}` : ''}</p>
              ${L.summaryZh ? `<p class="summary">💡 ${esc(L.summaryZh)}</p>` : ''}
            </div>
          </div>
          <div class="right">
            <div class="tabs" role="tablist">${MODES.map(m => `<button class="tab" role="tab" data-mode="${m.id}">${m.label}<small>${m.sub}</small></button>`).join('')}</div>
            <div id="modeBody"></div>
          </div>
        </div>
        <div class="playerbar" id="playerbar">
          <button class="pb-btn" data-pb="prev" aria-label="上一句">${ICON.prev}</button>
          <button class="pb-btn main" data-pb="play" aria-label="播放/暫停">${ICON.play}</button>
          <button class="pb-btn" data-pb="next" aria-label="下一句">${ICON.next}</button>
          <button class="pb-btn" data-pb="loop" aria-label="單句循環" aria-pressed="false" title="單句循環">${ICON.loop}</button>
          <button class="pb-rate" data-pb="rate" aria-label="播放速度">${store.prefs.rate}×</button>
        </div>`;
      P.mount(L);
      $('.tabs').onclick = e => { const t = e.target.closest('[data-mode]'); if (t) location.hash = `#/l/${id}/${t.dataset.mode}`; };
      $('#playerbar').onclick = onPlayerBar;
    }
    $$('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.mode === mode));
    // 跟讀/聽寫卡片自帶播放鈕，浮動播放列會擋住卡片 → 只在聽讀/單字模式顯示
    $('#playerbar').hidden = mode === 'shadow' || mode === 'dictation';
    P.onTick = null; P.onLineEnd = null; P.loopIdx = null; renderLoopBtn();
    ({ listen: modeListen, shadow: modeShadow, dictation: modeDictation, vocab: modeVocab }[mode] || modeListen)(L);
  }
  function setMode(m) { location.hash = `#/l/${view.lessonId}/${m}`; }

  // 目前「焦點句」：聽讀模式跟影片走；練習模式跟卡片走
  let focusIdx = 0;
  function onPlayerBar(e) {
    const b = e.target.closest('[data-pb]'); if (!b) return;
    const L = currentLesson(); const act = b.dataset.pb;
    const practice = view.mode === 'shadow' || view.mode === 'dictation';
    if (act === 'play') {
      if (practice) P.playing() ? P.yt.pauseVideo() : P.playLine(focusIdx);
      else P.toggle();
    }
    if (act === 'prev' || act === 'next') {
      const base = practice ? focusIdx : Math.max(0, P.cur);
      const k = Math.min(L.lines.length - 1, Math.max(0, base + (act === 'next' ? 1 : -1)));
      if (practice) { gotoPractice(k); P.playLine(k); }
      else { if (P.loopIdx != null) P.loopIdx = k; P.playFrom(k); }
    }
    if (act === 'loop') {
      if (P.loopIdx != null) { P.loopIdx = null; toast('單句循環：關'); }
      else {
        const k = practice ? focusIdx : Math.max(0, P.cur);
        P.loopIdx = k; toast(`單句循環：第 ${k + 1} 句`);
        if (practice) P.playLine(k); else if (!P.playing()) P.playFrom(k);
      }
      renderLoopBtn();
    }
    if (act === 'rate') {
      const rates = [1, 0.75, 0.5];
      const r = rates[(rates.indexOf(store.prefs.rate) + 1) % rates.length] || 1;
      P.setRate(r); b.textContent = `${r}×`; toast(r === 1 ? '正常速度' : `慢速 ${r}×`);
    }
  }
  function renderPlayBtn() { const b = $('[data-pb="play"]'); if (b) b.innerHTML = P.playing() ? ICON.pause : ICON.play; }
  function renderLoopBtn() { const b = $('[data-pb="loop"]'); if (b) b.setAttribute('aria-pressed', P.loopIdx != null); }
  let gotoPractice = () => { };

  function modeListen(L) {
    const pr = store.prefs, p = lp(L.id);
    const body = $('#modeBody');
    body.innerHTML = `
      <div class="mode-tip">${MODES[0].tip}</div>
      <div class="chips">
        <button class="chip" data-pref="hideEn" aria-pressed="${pr.hideEn}">🙈 蓋住英文</button>
        <button class="chip" data-pref="hideZh" aria-pressed="${pr.hideZh}">隱藏中文</button>
        <button class="chip" data-pref="follow" aria-pressed="${pr.follow}">自動捲動</button>
      </div>
      <div class="lines ${pr.hideEn ? 'hide-en' : ''} ${pr.hideZh ? 'hide-zh' : ''}" id="lines">
        ${L.lines.map((x, i) => {
          const best = Math.max(p.shadow[i] || 0, p.dict[i] || 0);
          return `<div class="line" data-i="${i}">
            <div class="ts">${fmt(x.t)}</div>
            <div><div class="en">${highlight(x, i)}</div><div class="zh">${esc(x.zh)}</div></div>
            ${best >= 70 ? `<span class="score-dot">${best}</span>` : ''}
          </div>`;
        }).join('')}
      </div>`;
    const lines = $('#lines');
    body.onclick = e => {
      const pref = e.target.closest('[data-pref]');
      if (pref) {
        const k = pref.dataset.pref; pr[k] = !pr[k]; save();
        pref.setAttribute('aria-pressed', pr[k]);
        lines.classList.toggle('hide-en', pr.hideEn); lines.classList.toggle('hide-zh', pr.hideZh);
        return;
      }
      const v = e.target.closest('.vocab');
      if (v && !(pr.hideEn && !v.closest('.line').classList.contains('active'))) {
        const line = L.lines[v.dataset.li]; openWord(line.vocab[v.dataset.vi], line, L.id, +v.dataset.li); return;
      }
      const ln = e.target.closest('.line');
      if (ln) { const i = +ln.dataset.i; p.last = i; save(); if (P.loopIdx != null) { P.loopIdx = i; } P.playFrom(i); }
    };
    body.onkeydown = e => { if (e.key === 'Enter' && e.target.classList.contains('vocab')) e.target.click(); };
    P.onTick = k => {
      $$('.line.active', lines).forEach(el => el.classList.remove('active'));
      if (k < 0) return;
      const el = lines.children[k]; if (!el) return;
      el.classList.add('active'); p.last = k; store.last.idx = k; save();
      if (pr.follow) {
        const r = el.getBoundingClientRect();
        const topSafe = window.innerWidth < 900 ? ($('.video-sticky').getBoundingClientRect().bottom + 8) : 80;
        if (r.top < topSafe || r.bottom > window.innerHeight - 100) {
          window.scrollTo({ top: window.scrollY + r.top - topSafe - 10, behavior: 'smooth' });
        }
      }
    };
    if (P.ready) P.onTick(P.lineAt(P.time()));
  }

  // 跟讀與聽寫共用的「單句卡片」框架
  function practiceShell(L, kind) {
    const p = lp(L.id); const scores = kind === 'shadow' ? p.shadow : p.dict;
    focusIdx = Math.min(p.last || 0, L.lines.length - 1);
    const body = $('#modeBody');
    const tip = MODES.find(m => m.id === kind).tip;
    const draw = () => {
      const i = focusIdx, x = L.lines[i];
      body.innerHTML = `
        <div class="mode-tip">${tip}</div>
        <div class="practice">
          <div class="p-top">
            <span class="p-count">第 ${i + 1} / ${L.lines.length} 句</span>
            <div class="p-nav">
              <button data-n="-1" ${i === 0 ? 'disabled' : ''} aria-label="上一句">${ICON.back}</button>
              <button data-n="1" ${i === L.lines.length - 1 ? 'disabled' : ''} aria-label="下一句" style="transform:scaleX(-1)">${ICON.back}</button>
            </div>
          </div>
          <div class="dots">${L.lines.map((_, k) => `<i class="${(scores[k] || 0) >= 80 ? 'ok' : (scores[k] || 0) >= 50 ? 'mid' : ''} ${k === i ? 'cur' : ''}" title="第 ${k + 1} 句"></i>`).join('')}</div>
          <div id="pcard"></div>
        </div>`;
      (kind === 'shadow' ? drawShadow : drawDictation)(L, i, scores, $('#pcard'), next);
    };
    const next = () => { if (focusIdx < L.lines.length - 1) { gotoPractice(focusIdx + 1); P.playLine(focusIdx); } else toast('🎉 這一課練完了！'); };
    gotoPractice = k => { focusIdx = k; p.last = k; store.last.idx = k; save(); if (P.loopIdx != null) P.loopIdx = k; draw(); };
    body.onclick = e => {
      const n = e.target.closest('[data-n]'); if (n && !n.disabled) { gotoPractice(focusIdx + +n.dataset.n); P.playLine(focusIdx); }
      const d = e.target.closest('.dots i'); if (d) { gotoPractice([...d.parentNode.children].indexOf(d)); P.playLine(focusIdx); }
    };
    draw();
  }

  function scoreHtml(score) {
    const cls = score >= 80 ? 'good' : score >= 50 ? 'mid' : 'low';
    const stars = score >= 95 ? 3 : score >= 80 ? 2 : score >= 50 ? 1 : 0;
    const praise = score >= 95 ? 'Perfect! 太棒了' : score >= 80 ? 'Great job! 過關' : score >= 50 ? '不錯，再一次會更好' : '再聽一次原音，慢慢來';
    return `<div class="scorebox"><span class="score ${cls}">${score}</span><div><div class="stars">${'★'.repeat(stars)}${'☆'.repeat(3 - stars)}</div><div class="praise">${praise}</div></div></div>`;
  }

  function drawShadow(L, i, scores, el, next) {
    const x = L.lines[i];
    const last = scores[i] != null ? `上次最佳 ${scores[i]} 分` : '';
    el.innerHTML = `
      ${wordsHtml({ disp: x.en.split(/\s+/), status: null })}
      <div class="target-zh">${esc(x.zh)}</div>
      <div class="actions">
        <button class="btn" data-a="orig">${ICON.play} 聽原音</button>
        <button class="btn" data-a="slow">${ICON.turtle} 慢速 0.75×</button>
        <button class="btn primary big" data-a="speak">${ICON.mic} 換我說</button>
      </div>
      <div class="result" id="res" hidden></div>
      <div style="text-align:center;color:var(--ink-3);font-size:12.5px;margin-top:10px">${last}</div>`;
    const res = $('#res', el), btn = $('[data-a="speak"]', el);
    el.onclick = e => {
      const a = e.target.closest('[data-a]'); if (!a) return;
      if (a.dataset.a === 'orig') P.playLine(i);
      if (a.dataset.a === 'slow') P.playLine(i, { rate: 0.75 });
      if (a.dataset.a === 'next') next();
      if (a.dataset.a === 'speak') {
        if (P.playing()) P.yt.pauseVideo();
        if (!SR) return recordSelf(btn, res);
        if (btn.classList.contains('recording')) { if (rec) rec.stop(); return; }
        btn.classList.add('recording'); btn.innerHTML = `${ICON.mic} 聆聽中…說完了點這裡評分`;
        res.hidden = false; res.innerHTML = '<div class="heard">請對著麥克風唸出上面的句子</div>';
        listen({
          maxMs: Math.min(25000, 6000 + x.en.split(/\s+/).length * 700),  // 依句長給時間
          onResult: txt => { res.innerHTML = `<div class="heard">聽到：<b>${esc(txt)}</b></div>`; },
          onError: err => {
            const msg = { 'not-allowed': '麥克風權限被拒絕，請到瀏覽器設定允許', 'no-speech': '沒有聽到聲音，再試一次', 'network': '語音辨識需要網路連線', 'audio-capture': '找不到麥克風' }[err] || `辨識失敗（${err}）`;
            res.innerHTML = `<div class="heard" style="color:var(--bad)">${msg}</div>`;
          },
          onEnd: txt => {
            btn.classList.remove('recording'); btn.innerHTML = `${ICON.mic} 再說一次`;
            if (!txt) {
              if (!res.querySelector('[style*="--bad"]')) res.innerHTML = '<div class="heard" style="color:var(--bad)">沒有聽到聲音，再按一次「再說一次」試試</div>';
              return;
            }
            const cmp = compare(x.en, txt);
            const best = Math.max(scores[i] || 0, cmp.score); scores[i] = best; save(); bumpToday();
            $('.target', el).outerHTML = wordsHtml(cmp);
            res.innerHTML = `${scoreHtml(cmp.score)}<div class="heard">聽到：<b>${esc(txt)}</b></div>
              ${cmp.score >= 80 ? `<button class="btn teal" data-a="next" style="width:100%;margin-top:10px">下一句 →</button>` : ''}`;
            const dot = $$('.dots i')[i]; if (dot) dot.className = `${best >= 80 ? 'ok' : best >= 50 ? 'mid' : ''} cur`;
          }
        });
      }
    };
  }

  function drawDictation(L, i, scores, el, next) {
    const x = L.lines[i];
    let hintLvl = 0;
    const words = x.en.split(/\s+/);
    const hint = () => hintLvl === 0 ? '' : words.map(w => {
      const core = w.replace(/[^A-Za-z0-9']/g, '');
      return hintLvl === 1 ? core[0] + '_'.repeat(Math.max(0, core.length - 1)) : core;
    }).join(' ');
    el.innerHTML = `
      <div class="actions" style="margin-bottom:12px">
        <button class="btn primary" data-a="orig">${ICON.play} 播放這句</button>
        <button class="btn" data-a="slow">${ICON.turtle} 慢速 0.75×</button>
      </div>
      <textarea class="dict-input" id="din" placeholder="把聽到的英文打在這裡…" autocapitalize="off" autocomplete="off" autocorrect="off" spellcheck="false"></textarea>
      <div class="actions">
        <button class="btn" data-a="hint">💡 提示</button>
        <button class="btn teal" data-a="check">✓ 檢查</button>
      </div>
      <div id="hintBox" style="margin-top:10px;color:var(--ink-2);font-weight:700;letter-spacing:.5px" hidden></div>
      <div class="result" id="res" hidden></div>`;
    const din = $('#din', el), res = $('#res', el);
    setTimeout(() => P.playLine(i), 300);
    din.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); check(); } });
    const check = () => {
      if (!din.value.trim()) return toast('先打一些字再檢查');
      const cmp = compare(x.en, din.value);
      const penalty = hintLvl * 10;
      const score = Math.max(0, cmp.score - penalty);
      const best = Math.max(scores[i] || 0, score); scores[i] = best; save(); bumpToday();
      res.hidden = false;
      res.innerHTML = `${scoreHtml(score)}${penalty ? `<div class="heard">（用了提示 −${penalty}）</div>` : ''}
        ${wordsHtml(cmp)}<div class="target-zh" style="margin:0">${esc(x.zh)}</div>
        <div class="actions" style="margin-top:10px"><button class="btn" data-a="orig">${ICON.play} 再聽一次</button><button class="btn teal" data-a="next">下一句 →</button></div>`;
      const dot = $$('.dots i')[i]; if (dot) dot.className = `${best >= 80 ? 'ok' : best >= 50 ? 'mid' : ''} cur`;
    };
    el.onclick = e => {
      const a = e.target.closest('[data-a]'); if (!a) return;
      if (a.dataset.a === 'orig') P.playLine(i);
      if (a.dataset.a === 'slow') P.playLine(i, { rate: 0.75 });
      if (a.dataset.a === 'check') check();
      if (a.dataset.a === 'next') next();
      if (a.dataset.a === 'hint') {
        hintLvl = Math.min(2, hintLvl + 1);
        const hb = $('#hintBox', el); hb.hidden = false; hb.textContent = (hintLvl === 1 ? '字首提示：' : '完整答案：') + hint();
        a.textContent = hintLvl === 1 ? '💡 看答案' : '💡 已顯示';
        if (hintLvl === 2) a.disabled = true;
      }
    };
  }

  function modeShadow(L) {
    if (!SR) toast('這個瀏覽器不支援語音評分，會改用「錄音自己聽」。建議用 Chrome 或 iPhone Safari', 4500);
    practiceShell(L, 'shadow');
  }
  function modeDictation(L) { practiceShell(L, 'dictation'); }

  function modeVocab(L) {
    const items = [];
    const seen = new Set();
    L.lines.forEach((x, li) => x.vocab.forEach(v => { if (!seen.has(v.lemma)) { seen.add(v.lemma); items.push({ ...v, lesson: L.id, li }); } }));
    const body = $('#modeBody');
    body.innerHTML = `<div class="mode-tip">${MODES[3].tip}</div>
      <div class="chips"><button class="chip" data-all="1">⭐ 全部加入生字本</button></div>
      ${vocabListHtml(items, false)}`;
    body.onclick = e => {
      if (e.target.closest('[data-all]')) {
        items.forEach(v => { if (!store.words[v.lemma]) store.words[v.lemma] = { ...v, added: Date.now() }; });
        save(); renderHeader(); toast(`已加入 ${items.length} 個字`); modeVocab(L); return;
      }
      handleVocabListClick(e);
    };
  }

  // ---------- router ----------
  function route() {
    closeSheet();
    if (rec) rec.abort();
    const h = location.hash.replace(/^#\/?/, '').split('/');
    if (h[0] === 'l' && h[1]) {
      const mode = MODES.some(m => m.id === h[2]) ? h[2] : 'listen';
      app.onclick = null;
      renderLesson(h[1], mode);
      window.scrollTo({ top: 0 });
      return;
    }
    if (h[0] === 's' && h[1] && DATA.series.some(se => se.id === h[1])) { store.prefs.series = h[1]; save(); }
    view = { name: h[0] === 'words' ? 'words' : 'home' };
    app.onclick = null;
    if (h[0] === 'words') renderWords(); else renderHome();
    window.scrollTo({ top: 0 });
  }

  // ---------- boot ----------
  renderHeader();
  fetch('data/lessons.json').then(r => r.json()).then(d => {
    DATA = d;
    window.addEventListener('hashchange', route);
    route();
  }).catch(() => { app.innerHTML = '<div class="empty"><b>😵</b>課程資料載入失敗，請檢查網路後重新整理。</div>'; });
  if ('speechSynthesis' in window) speechSynthesis.getVoices();
})();
