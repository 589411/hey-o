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
tools/make_icons.py                    ← 產生 App 圖示
sw.js  manifest.webmanifest  CNAME     PWA + GitHub Pages
docs/gemini-draft/                     ← 最初 Gemini 草稿（僅供參考，內容有誤）
```

## 新增一課
1. 抓字幕（yt-dlp，ios client 才拿得到）：
   ```
   yt-dlp --extractor-args "youtube:player_client=ios" --ignore-no-formats-error --skip-download \
     --write-auto-subs --sub-langs en --sub-format json3 -o "%(id)s" "https://www.youtube.com/watch?v=<ID>"
   python3 tools/extract_timings.py <ID>.en.json3
   ```
2. 寫 `content/NN-<id>.json`：`lines` 每句 `[英文, 中文, [[原形於句中, lemma, 詞性, 音標, 中譯], ...]]`
3. `python3 tools/build_data.py`（對齊率低會印 ⚠）
4. `sw.js` 的 `CACHE` 升版，commit & push

影片版權屬 Saddleback Kids，本站僅以 YouTube 官方嵌入播放。
