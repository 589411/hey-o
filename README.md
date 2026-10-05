# Hey-O! 英聽口說

用 Saddleback Kids《Hey-O! Stories of the Bible》動畫練英聽與口說的 PWA。
線上：https://hey-o.launchdock.app

## 功能
- **聽讀**：影片＋逐字稿同步高亮、自動捲動；「蓋住英文」盲聽、隱藏中文；黃色底線單字可點（音標、詞性、中譯、發音、收藏）
- **跟讀**：單句播放自動停 → 「換我說」語音辨識 → 逐字比對上色＋分數（不支援辨識的瀏覽器改成錄音自己聽）
- **聽寫**：只聽不看，打出句子後逐字批改（容許 1 個字母拼錯、數字/縮寫自動對齊），可用提示（扣分）
- **單字 / 生字本**：每課生字清單、⭐ 收藏、閃卡複習
- 播放列：上一句/下一句、單句循環、1× / 0.75× / 0.5×
- 進度、分數、連續天數存在 localStorage（只在本機）；可加到主畫面、離線開啟（影片仍需網路）

## 結構
```
index.html  css/app.css  js/app.js     純前端、無 build
data/lessons.json                      ← 由 tools/build_data.py 產生，勿手改
content/NN-<id>.json                   ← 每課人工校對的句子＋中譯＋單字（唯一要編的地方）
tools/timings/<videoId>.json           ← YouTube 自動字幕的逐字時間軸
tools/build_data.py                    ← 把 content 句子對齊 timings，算出每句 t/end
tools/extract_timings.py               ← json3 字幕 → timings
tools/add_lesson.py                    ← 擴充課程（yt-dlp 抓字幕 + agy 整理翻譯 + 驗證）
tools/make_icons.py                    ← 產生 App 圖示
sw.js  manifest.webmanifest  CNAME     PWA + GitHub Pages
docs/gemini-draft/                     ← 最初 Gemini 草稿（僅供參考，內容有誤）
```

## 擴充課程（yt-dlp + agy）
```
python3 tools/add_lesson.py --list                    # 頻道上還沒收錄的單集（✓ = 已收錄）
python3 tools/add_lesson.py <videoId> [<videoId>…] --keep-going
python3 tools/add_lesson.py <videoId> --model "Claude Opus 4.6 (Thinking)"   # 換 agy 模型
```
分工：
1. **yt-dlp（確定性）**：驗證影片 ID、頻道、可否嵌入；抓英文自動字幕的逐字時間 → `tools/timings/`
2. **agy（LLM）**：把無標點字幕整理成句子、校正人名、譯成台灣繁中（和合本譯名）、挑單字＋音標
3. **程式驗證**：英文與字幕吻合度 ≥ 90%、字幕覆蓋率 ≥ 85%、每句 ≥ 50%、單字必須出現在句中；沒過會把錯誤回饋給 agy 重試一次，再沒過就不寫入
4. 寫 `content/NN-<id>.json` → 重建 `data/lessons.json`（依聖經書卷自動排序）→ `sw.js` CACHE 升版

**為什麼不讓 agy 直接「抓 YouTube 字幕」**：LLM 會編影片 ID、時間碼與句子（Gemini 初稿就這樣）。抓取交給工具、理解交給 LLM、把關交給程式。

需要 `yt-dlp`（`brew install yt-dlp`，或 `YTDLP=/path/to/yt-dlp`）與已登入的 `agy`。YouTube 連抓會 429，腳本會自動退避重試。
新增後請人工抽查翻譯再 commit。

影片版權屬 Saddleback Kids，本站僅以 YouTube 官方嵌入播放。
