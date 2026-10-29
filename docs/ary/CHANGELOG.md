# ARY fork 變更紀錄（ARYisme/OneManCompany，branch `ary-readable-ui`）

此 fork 以上游 1mancompany/OneManCompany `3fde188` 為基底（Apache-2.0）。以下為 ARY 的修改，時間為 AEDT。

## 2026-10-29

- 新增本地人才包「企劃」（`ary-product-planner`，模型 `foundry-gx10-main`）：產品與服務企劃、市場切入方案、
  專案規劃與時程、提案書／企劃書、成本效益評估 5 個 SOP skills，每個含交件格式與品質檢查清單；
  與市場研究員（00006）合作。role `Planner` → General 部門，**沒有 bash**；web_fetch 由 manifest 授權；
  Email 只存草稿。參考 MetaGPT、agency-agents、CrewAI、ChatDev 與 OMC Talent Market 的 PM 做法，
  詳見 [product-planner.md](product-planner.md)。只是資料（人才包），沒有改程式。
- 部署（Harbor，22:18–22:21 AEDT，King ops `up --build`）：OMC 映像改用 `a1d8342`，映像標籤改成
  `harbor-onemancompany:0.7.113-a1d8342`（`0.7.113` 是上游版本，後面是實際 fork commit；之前的 `0.7.113-3fde188`
  其實跑的是 5998b66）。實際停機約 20 秒（22:20:39 舊容器停止 → 22:20:59 新容器 healthy）。
  備份：容器內 `/workspace/.onemancompany/backups/omc-data-pre-planner-rebuild-20261029T111735Z.tgz`；
  Harbor stack 目錄 `compose.yaml`／`.env`／`.env.example` 的 `.bak-20261029T111735Z-pre-planner`；
  回滾映像標籤 `harbor-onemancompany:rollback-pre-planner-20261029T111735Z`（＝ 5998b66 的映像）。
- EA（00004）模型改為 `foundry-gx10-main`（資料變更，不在 git）：避免 `foundry-gx10-fast` 的
  「Image tokens exceed context capacity」400 且 fast 沒有 fallback。備份
  `backups/20261029-2208-ary/employees/00004/profile.yaml`。
- 5998b66 security(bash)：option D，擋 Gmail／secret 繞道、bash 降權為 nobody（Cursor）。
- 5d7e3d2 fix(policy)：禁止謊報完成與繞過 Gmail 工具（EA 事件後，Cursor）。詳見 [incident-20261029-gmail-bypass.md](incident-20261029-gmail-bypass.md)。

## 2026-10-28

- Gmail 只能寫草稿（uzena.nari@gmail.com）：刪除 `gmail_send`、`gmail_reply`；`gmail_create_draft` 支援回覆同串（threadId、In-Reply-To、References）、cc/bcc、UTF-8 中文、From 固定 uzena.nari，回傳繁中「請 ARY 自己審核寄出」提示；`_api_request` 拒絕任何 send 路徑。權限改 `gmail.readonly` + `gmail.compose`（不寄信的保證來自程式碼）。OAuth：client 憑證可由唯讀 secret 檔提供（`GOOGLE_OAUTH_CLIENT_FILE`），遠端授權改「貼回跳轉網址」（`POST /api/tools/{id}/oauth/exchange`，不開新 port）。**尚未部署**。詳見 [email-drafts-only.md](email-drafts-only.md)。
- `web_fetch` 工具：市場研究員（`ary-market-researcher`）可打開公開網頁讀全文。
  後端 crawl4ai（有 token 時）＋標準庫 fallback；SSRF 防護、20 秒 timeout、2 MB 上限。
  詳見 [web-tools.md](web-tools.md)。
- 部署（Harbor，22:01–22:04 AEDT，King ops `up --build`）：OMC 映像改用 `e12cd9c`；crawl4ai token 以
  唯讀 secret 檔 `/run/secrets/crawl4ai_api_token`（`CRAWL4AI_API_TOKEN_FILE`）提供，不放 data `.env`、不進 git／映像。
  回滾映像標籤 `harbor-onemancompany:rollback-pre-webfetch-20261028`。實測：Coles 商品頁、ABS 可讀；
  Woolworths 與 Coles 分類頁仍被防爬擋下。
- `38f8e27` talents：補上 6 位 ary-* 員工的 SOP skills。
- `63509d1` talents：新增 6 位本地繁中員工包（ary-coder、ary-market-researcher、ary-copywriter、
  ary-vic-regulation、ary-tw-stock、ary-secretary）。
- `6d10595` ui：員工中文名稱與對話以 opencc-js 轉為台灣繁體（只影響顯示）。
- `7ea1643` ui：全站字體統一為 Noto Sans TC，移除像素字體（CSS、canvas、G6、xterm），`lang=zh-Hant`。
- `7fa82ae` ui：系統／繁中可讀字體與手機單欄版面。
