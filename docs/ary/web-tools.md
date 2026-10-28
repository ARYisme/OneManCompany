# 員工上網工具：`web_fetch`（ARY fork）

> 適用：ARY 的 OneManCompany fork（`ARYisme/OneManCompany`，branch `ary-readable-ui`），
> 部署在 Harbor（192.168.11.20）的 `harbor-onemancompany` 容器。
> 建立日期：2026-10-28（AEDT）。

## 1. 這是什麼、為什麼要做

市場研究員（`ary-market-researcher`，目前在職為 **00006 市場研究員（花满）**）的 SOP 要求
「先打開我們自己的網站、比對 Coles／Woolworths 價格、引用 ABS 數據，每個數字附來源與日期」。
OMC 原本只有 `web_search`（DuckDuckGo 搜尋摘要），**沒有能打開網頁全文的工具**，
所以員工只能看搜尋摘要、無法讀到頁面內容。

`web_fetch(url, max_chars=20000)` 補上這一塊：打開**一個公開網頁**，回傳可讀文字／markdown，
並附 `final_url`、`fetched_at`、`http_status`、`backend`，讓員工可以寫出有來源的結論。

| 工具 | 功能 | 後端 | 誰有 |
|---|---|---|---|
| `web_search` | 搜尋，回傳標題＋摘要＋網址 | DuckDuckGo（`ddgs` 套件，免 key，OMC 內建） | 所有員工（OMC 原生 company asset tool） |
| `web_fetch` | 打開單一網頁讀全文 | crawl4ai（有 token 時）→ 失敗時改用 Python 標準庫抓取 | 只有被授權的員工（見第 4 節） |

## 2. 後端設計

1. **crawl4ai（首選）**：`POST {CRAWL4AI_BASE_URL}/md`，body `{"url": <已驗證的網址>, "f": "fit", "c": "0"}`，
   header `Authorization: Bearer <token>`，回傳 markdown（會執行 JavaScript）。
   - 預設 `CRAWL4AI_BASE_URL=http://192.168.11.20:11235`（Harbor 本機的 crawl4ai，stack 在
     `harbor-infra/stacks/ai/crawl4ai`，image `unclecode/crawl4ai` 0.9.3）。
     AUNODE 也有一份（`192.168.1.151:11235`，`AUNODE_infra/stacks/ai/crawl4ai`），一樣可從 Harbor 連到。
   - `GET /health` 公開；其他路由都要 Bearer token。
   - token 讀取順序：環境變數 `CRAWL4AI_API_TOKEN` → `CRAWL4AI_API_TOKEN_FILE` 指向的檔案。
     **token 不會寫進 log、不會回傳給員工、不放進 git。**
   - 若沒有 token、crawl4ai 掛掉或回錯，會自動 fallback，並在 `note` 欄位說明原因。
2. **標準庫 fallback**：`http.client` + `ssl` + `html.parser`，不執行 JavaScript。
   HTML 會轉成純文字（保留標題 `#`、清單 `-`、表格 `|`）。

只用 Python 標準庫與 image 內已有的 `langchain_core` / `loguru`，**沒有新增任何套件或付費／雲端 API key**。

## 3. 安全限制（兩個後端都適用）

- 只允許 `http` / `https`，只允許 port **80 / 443**，網址不得含帳密（`user:pw@`）。
- **SSRF 防護**：主機名稱先做 DNS 解析，**所有**解析出的 IP 都必須是公開 IP；以下一律拒絕：
  private（10/8、172.16/12、192.168/16）、loopback（127/8、::1）、link-local（169.254/16、fe80::/10，含雲端 metadata）、
  CGNAT／Tailscale（100.64.0.0/10）、Tailscale IPv6（fd7a:115c:a1e0::/48）、ULA、multicast、reserved、
  IPv4-mapped IPv6（`::ffff:127.0.0.1`），以及單段主機名（`aunode`、`harbor`）和
  `.local/.lan/.internal/.home.arpa/.ts.net/.localhost` 等內網後綴。
  → 員工**不能**透過這個工具碰到 LiteLLM（192.168.11.8:4000）、aunode、Harbor、orin 或 Tailscale 網段。
- 標準庫抓取時**直接連線到已驗證的 IP**（避免檢查後 DNS 被換掉的 rebinding），
  並且**每一次 redirect 都重新驗證**（最多 5 次）。
- 交給 crawl4ai 之前，先用安全抓取跟完 redirect，再驗證**最終網址**一次；
  crawl4ai 端點本身是這個工具唯一允許連線的內部位址。
- 只做 GET；不帶 cookie、不帶任何帳密、不走 proxy；User-Agent 明確標示
  `OMC-MarketResearcher/1.0 ... web_fetch`。
- timeout 約 20 秒（`WEB_FETCH_TIMEOUT`，crawl4ai 另有 `CRAWL4AI_TIMEOUT` 預設 25 秒）；
  回應上限 2 MB（gzip 也有限制解壓大小）；回傳文字預設 20,000 字、最多 60,000 字。
- 只接受文字類內容（`text/*`、HTML、JSON、XML、RSS）；圖片、PDF、壓縮檔等一律拒絕，不下載檔案。

## 4. 誰有這個工具、怎麼開關

OMC 的正規機制是 **company asset tool**：
`/workspace/.onemancompany/company/assets/tools/<tool>/tool.yaml` + `<tool>.py`（`type: langchain_module`），
OMC 啟動時由 `ToolRegistry.load_asset_tools()` 載入。
`tool.yaml` 有 `source_talent` 時屬於「人才自帶工具」，只有 `allowed_users` 名單裡的員工能用。

目前狀態（2026-10-28）：

- `assets/tools/web_fetch/tool.yaml`：`source_talent: ary-market-researcher`、`allowed_users: ['00006']`。
- `employees/00006/tools/manifest.yaml`：`custom_tools: [web_fetch]`（解雇時 `termination.py` 會依此自動移除授權）。
- **注意**：OMC 內建規則是 **EA（00004）可以使用所有工具**（`ToolRegistry._is_allowed` 對 role EA 直接放行），
  所以 EA 也看得到 `web_fetch`。這是 OMC 原本的設計，這次沒有改後端。

人才定義：`src/onemancompany/talent_market/talents/ary-market-researcher/tools/web_fetch/`
（`tool.yaml` + `web_fetch.py`），`tools/manifest.yaml` 的 `custom_tools: [web_fetch]`。
之後**新聘**的市場研究員，onboarding（`copy_talent_assets`）會把工具複製到 `assets/tools/`（已存在就不覆蓋）
並呼叫 `register_tool_user()` 把新員工加進 `allowed_users`。
人才資料夾是烤在 image 裡的，所以「新聘也自動有」要等下一次 image rebuild 才生效；
現有的 00006 已經透過 data volume 直接生效，不需要 rebuild。

開關方式（都在容器內、data volume 上操作）：

```bash
# 給某位員工（例：00007）
cd /workspace && python -c "from onemancompany.agents.onboarding import register_tool_user; register_tool_user('web_fetch','00007')"
# 拿掉某位員工
cd /workspace && python -c "from onemancompany.agents.onboarding import unregister_tool_user; unregister_tool_user('web_fetch','00006')"
```

改完 `tool.yaml` 後要讓 OMC 重新載入工具：在 UI 按「套用程式更新」，或
`POST /api/admin/apply-code-update`（OMC 自己的 graceful restart，`os.execv`，約 5 秒，
容器不重建、RestartCount 不變；若有任務在跑會延後到空閒時）。

## 5. crawl4ai 已啟用（2026-10-28，token 檔方式）

2026-10-28 22:01–22:04 AEDT 經 ARY 同意，以 King ops 重建 OMC 容器啟用 crawl4ai。實際做法（Harbor
`harbor-infra/stacks/ai/onemancompany/`，此目錄不是 git repo）：

1. **token 檔**：`secrets/crawl4ai_api_token`（目錄 700、檔案 600、owner `ary`），內容只有 token 一行，
   由 crawl4ai stack 的 `.env`（`CRAWL4AI_API_TOKEN`）用管線抽出，過程不顯示 token。
   **token 不進 git、不進映像**：stack 目錄新增 `.gitignore`（`secrets/`），`.dockerignore` 也加了 `secrets/`。
2. **compose.yaml**（`onemancompany` 服務）：
   ```yaml
   environment:
     CRAWL4AI_BASE_URL: http://192.168.11.20:11235
     CRAWL4AI_API_TOKEN_FILE: /run/secrets/crawl4ai_api_token
   volumes:
     - ./secrets/crawl4ai_api_token:/run/secrets/crawl4ai_api_token:ro
   ```
   同時 build arg `OMC_REF` 改為 `e12cd9c0da6351a4e08cb96f91068829e851c96b`（映像內含本工具的人才包）。
3. **部署**：`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up --build`（不要直接 docker compose）。
4. **OMC data `.env` 沒有放 token**，重建前後 hash 相同（entrypoint 只在檔案不存在時才產生）。

`web_fetch` 讀 token 的順序：環境變數 `CRAWL4AI_API_TOKEN` → `CRAWL4AI_API_TOKEN_FILE` 指向的檔案。
都沒有就走標準庫 fallback。crawl4ai 失敗（例如 HTTP 502）也會自動 fallback，並在 `note` 註明原因。

換 token：用「原地覆寫」更新 `secrets/crawl4ai_api_token`（例如 `cat > 檔案`，保持 600；不要用會換掉檔案 inode 的編輯器，否則單檔 bind mount 仍指向舊檔），再 King ops `restart`，不必 rebuild。

## 6. 怎麼測試

在 OMC 的一對一聊天（要開 tools）對 00006 說：

> 請用 web_fetch 打開 https://www.abs.gov.au/ ，用三點摘要並附來源網址與擷取時間。

預期：回覆有內容、附 `https://www.abs.gov.au/` 與擷取時間；容器 log 會有
`[web_fetch] url=https://www.abs.gov.au/ backend=crawl4ai status=200`。

SSRF 測試（應該都回 `status: blocked`）：`http://192.168.11.8:4000`、`http://127.0.0.1`、
`http://192.168.11.20/`、`http://100.97.221.59/`、`http://aunode/`、`http://169.254.169.254/`。

## 7. 已知限制

2026-10-28 重建後實測（直接呼叫工具，容器內）：

| 網址 | 後端 | 結果 |
|---|---|---|
| Coles 商品頁 `coles.com.au/product/coles-full-cream-milk-3l-8150288` | crawl4ai | ✅ 200，有標題、價格（$4.95、$1.65/1L） |
| Coles 分類頁 `coles.com.au/browse/dairy-eggs-fridge/milk` | crawl4ai 502 → stdlib | ⚠️ 200 但內容空白 |
| Woolworths 分類頁／商品頁 | crawl4ai 502 → stdlib | ❌ 403 Access Denied（crawl4ai 端是 `ERR_HTTP2_PROTOCOL_ERROR`，Akamai 防爬） |
| ABS CPI 最新發布 | crawl4ai | ✅ 200 |

- **防爬封鎖**：Woolworths 目前 crawl4ai 和 fallback 都讀不到；Coles 分類頁也讀不到。
  工具會回 `http_error`／`empty`，並提醒員工**不可編造數字**，改用 `web_search` 摘要（附來源）或標示「無法取得」。
- **robots.txt／網站條款**：工具不會自動讀 robots.txt。請只做少量、人工等級的查詢，
  不要大量爬取；Coles／Woolworths 的條款限制自動化存取，正式價格監控請改用授權資料或人工抽查。
- **crawl4ai 內部行為**：交給 crawl4ai 的最終網址已驗證，但頁面裡的 JavaScript 由 crawl4ai 的瀏覽器執行，
  它能連到哪裡由 crawl4ai 容器的網路決定，不在本工具控制範圍。建議之後替 crawl4ai 容器加出站防火牆（擋 RFC1918／Tailscale）。
- 員工本身不能直接打 crawl4ai：`http://192.168.11.20:11235` 對 `web_fetch` 一樣被擋（只允許 80/443）。
- `fetched_at` 用容器時區（UTC）。
- 不支援登入、表單、POST、付費牆內容。

## 8. 回滾

只拿掉工具（不重建）：

```bash
# 容器內（只動 data volume，不動其他員工）
rm -r /workspace/.onemancompany/company/assets/tools/web_fetch
rm -r /workspace/.onemancompany/company/human_resource/employees/00006/tools
# 然後 UI「套用程式更新」或 POST /api/admin/apply-code-update（OMC 自己 os.execv，約 5 秒）
```

回到啟用 crawl4ai 之前的容器（Harbor stack 目錄）：

```bash
cp compose.yaml.bak-20261028-110107-webfetch compose.yaml
cp .dockerignore.bak-20261028-110107-webfetch .dockerignore
docker tag harbor-onemancompany:rollback-pre-webfetch-20261028 harbor-onemancompany:0.7.113-3fde188
APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up   # 不加 --build，否則會用舊 OMC_REF 重建
```

（備份檔名的時間是 Harbor 的 UTC，= 22:01 AEDT。）`secrets/` 可留著；不掛載就不會被讀到。

程式碼回滾：`git revert <本次 commit>`（只影響人才資料夾與 docs，不影響後端）。

## 相關檔案

- `src/onemancompany/talent_market/talents/ary-market-researcher/tools/web_fetch/web_fetch.py`
- `src/onemancompany/talent_market/talents/ary-market-researcher/tools/web_fetch/tool.yaml`
- `src/onemancompany/talent_market/talents/ary-market-researcher/tools/manifest.yaml`
- `docs/ary/CHANGELOG.md`
