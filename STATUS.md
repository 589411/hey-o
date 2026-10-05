# STATUS — hey-o

**更新：2026-10-05**

## 現況
- v1 完成：9 課（301 句、真實字幕對齊時間軸）、聽讀/跟讀/聽寫/單字四模式、生字本閃卡、PWA。
- Repo：github.com/589411/hey-o（GitHub Pages, main / root），CNAME = hey-o.launchdock.app
- Gemini 草稿問題已修正：原稿第 4 課（BCipIdfSae4）不是 Saddleback 的影片、第 10 課 ID 不存在，已換成官方 9rYT1co-Y-U、cgJJD-imOMs；原稿逐字稿只有 6–9 句/課且時間碼多半不準，已改用 YouTube 字幕重做。

- 2026-10-05：DNS 已加、Pages 重設 cname 踢出憑證（approved, 到期 2027-01-02）、Enforce HTTPS 已開；線上 200、http→https 301、404 正常。已上架 lab.launchdock.app（id `hey-o-english`）。

- 2026-10-05：新增擴充工具 `tools/add_lesson.py`（yt-dlp 抓字幕 → agy 整理/中譯/選字 → fidelity/coverage 驗證）。用它加了 5 課（該隱與亞伯、約瑟的彩衣、十誡、揀選大衛作王、主禱文），全部吻合度 ≥ 99%；目前 14 課 407 句，依聖經書卷自動排序。

- 2026-10-05：臉書分享文 Joseph 已手動發佈。

- 2026-10-05：跟讀加保險（靜默 1.5s 自動評分、8s 沒出聲結束、依句長最長時限、iOS onend 不回的 watchdog、可手動按「說完了」），用模擬辨識器驗證三種情境皆通過；sw v4。

- 2026-10-05：新增第二系列「Bill Johnson 講道」（進階）。content 改成 `content/<series>/` + `content/series.json`；講道依 YouTube 章節自動切 3–6 分鐘一段（clipStart/clipEnd 只播該段）。agy 做了 13 課（完整講道「每天如何聆聽神的聲音」9 段＋短片「憂慮如何扼殺神的應許」＋「容易被冒犯的危險」3 段），全部吻合度 97–99%。現共 2 系列 27 課 1038 句。修了 bump_sw 會清空 index.html 的 bug（未上線前抓到）；css/js 加 ?v= 與 SW 同步升版。

## 卡在哪
- 「Stories from Genesis」(K6IA0Uj1JdY) 抓字幕一直 429，暫未收錄（內容與亞當夏娃/挪亞重疊）。
- 影片播放在自動化瀏覽器（背景視窗）無法實測；需在手機/桌機實際點播驗證：句子高亮跟隨、單句自動停、循環。

## 下一個具體動作
1. 開 https://hey-o.launchdock.app 實測 iPhone Safari：點句播放、跟讀語音評分（麥克風權限）、加入主畫面。
2. 繼續擴充：`python3 tools/add_lesson.py --series <heyo|bill-johnson> --list` 挑還沒收錄的單集 → `add_lesson.py --series … <id…> --keep-going`（講道先 `--plan` 看切段） → 抽查翻譯 → push。yt-dlp 目前在 scratchpad venv，正式用請 `brew install yt-dlp`。
