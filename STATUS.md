# STATUS — hey-o

**更新：2026-10-04**

## 現況
- v1 完成：9 課（301 句、真實字幕對齊時間軸）、聽讀/跟讀/聽寫/單字四模式、生字本閃卡、PWA。
- Repo：github.com/589411/hey-o（GitHub Pages, main / root），CNAME = hey-o.launchdock.app
- Gemini 草稿問題已修正：原稿第 4 課（BCipIdfSae4）不是 Saddleback 的影片、第 10 課 ID 不存在，已換成官方 9rYT1co-Y-U、cgJJD-imOMs；原稿逐字稿只有 6–9 句/課且時間碼多半不準，已改用 YouTube 字幕重做。

## 卡在哪
- Cloudflare DNS 尚未加：`hey-o` CNAME → `589411.github.io`（**DNS only 灰雲**）。加好後到 repo Settings → Pages 勾 Enforce HTTPS。
- 「Stories from Genesis」(K6IA0Uj1JdY) 抓字幕一直 429，暫未收錄（內容與亞當夏娃/挪亞重疊）。
- 影片播放在自動化瀏覽器（背景視窗）無法實測；需在手機/桌機實際點播驗證：句子高亮跟隨、單句自動停、循環。

## 下一個具體動作
1. 加 Cloudflare DNS → 開 https://hey-o.launchdock.app 實測 iPhone Safari：點句播放、跟讀語音評分（麥克風權限）、加入主畫面。
2. 視需要再加更多 Hey-O 課（照 README「新增一課」）。
