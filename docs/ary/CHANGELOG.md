# ARY fork 變更紀錄（ARYisme/OneManCompany，branch `ary-readable-ui`）

此 fork 以上游 1mancompany/OneManCompany `3fde188` 為基底（Apache-2.0）。以下為 ARY 的修改，時間為 AEDT。

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
