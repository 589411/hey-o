# hey-o — 給 AI 的 repo 規則
- 純靜態站（GitHub Pages），不要引入 build 工具或框架。
- 課程內容只改 `content/*.json`，再跑 `python3 tools/build_data.py` 產生 `data/lessons.json`；不要手改 data。
- 動到要離線快取的檔案 → `sw.js` 的 `CACHE` 升版。
- 中文用台灣繁體；聖經人名地名用和合本譯名。
