# OMC Email：只能寫草稿（uzena.nari@gmail.com）

ARY 決定（2026-10-28）：OMC 的 email **只接 `uzena.nari@gmail.com`**，用 OMC 原本的 Gmail 工具；
**員工只能寫草稿，ARY 自己看過再自己按寄出**。iCloud（hello@uzena.com.au 等）暫不接。

## 1. 用途

員工（HR、EA、CSO、COO、市場研究員…）可以：

| 工具 | 功能 |
|---|---|
| `gmail_search` | 用 Gmail 搜尋語法找信（唯讀） |
| `gmail_read` / `gmail_read_thread` | 讀單封信／整串對話（唯讀） |
| `gmail_create_draft` | 建立**草稿**：新信或「回覆某封信」（同一串、帶 In-Reply-To / References）、cc、bcc、附件（LangChain 版）、中文主旨與內文（UTF-8） |
| `gmail_get_profile` / `gmail_list_labels` | 查帳號、列標籤 |

**沒有** `gmail_send`、`gmail_reply`（原本的「回覆並寄出」）——兩個都刪掉了。

每次建立草稿，工具都會回傳繁中提示：「草稿已存到 uzena.nari@gmail.com 的 Gmail『草稿』匣，尚未寄出。
請 ARY 親自檢查後自己按『傳送』…」，並要求員工用 `report_to_ceo()` 通知 ARY 有草稿等審核。
寄件人（From）固定是 `uzena.nari@gmail.com`。

## 2. 「只能寫草稿」的保證從哪裡來

**保證來自程式碼，不是來自 Google 權限範圍。** 權限用 `gmail.readonly` + `gmail.compose`
（比原本的 `gmail.modify` 小：不能刪信、改標籤、移到垃圾桶），但 `gmail.compose` 在 Google 那邊
**其實允許寄信**（Google 沒有「只能建草稿」的範圍）。所以靠下面幾層：

1. `gmail.py` / `mcp_server.py` 沒有任何呼叫 `messages.send` 或 `drafts.send` 的程式。
   `mcp_server.py` 不再有自己的 HTTP 程式，全部呼叫 `gmail.py` 的同一套函式。
2. `gmail.py` 的 `_api_request()` 有防呆：路徑結尾是 `send`（或含 `/send`）一律拒絕；
   `POST` 只允許 `drafts`；`PUT`/`DELETE`/`PATCH` 全部拒絕。就算以後有人加了新函式，也送不出去。
3. 建草稿前會檢查授權的帳號是不是 `uzena.nari@gmail.com`，不是就拒絕。
4. 其他會碰到 Gmail 的地方都檢查過：HOLDING 任務的 reply poller（`core/vessel.py`）只是派
   「去看這串有沒有回信」的任務給員工，自己不寄信；`core/automation.py` 的 Gmail Pub/Sub 只收通知；
   兩個範本（`templates/*.md`）只是文字。`company/shared_prompts/tool_usage.md` 裡的 `gmail_send`
   也改成只寫草稿。
5. 單元測試 `tests/unit/test_gmail_drafts_only.py`：檢查工具清單裡沒有 send/reply、原始碼沒有
   `messages/send`/`drafts/send`、`_api_request` 對 send/其他寫入一律拒絕且不連網。

驗證指令（應該只看到註解和防呆那兩行）：

```bash
grep -rnE "messages/send|drafts/send|messages\.send|drafts\.send|/send\b" src company frontend
grep -rnE "gmail_send|gmail_reply" src company frontend      # 應該沒有結果
```

> 限制：員工如果有 shell／檔案工具，理論上能讀到容器裡的 token 快取自己打 API。這跟
> crawl4ai token 的風險同一級；真正的最後一道防線是「Google 帳號權限隨時可撤銷」（第 6 節）。
> 2026-10-29：EA 曾謊報刪草稿並自寫 `gmail_delete.py`（未跑成）。已刪檔並強化提示詞／工作原則；
> 硬隔離（bash／token）方案見 `docs/ary/incident-20261029-gmail-bypass.md`，等 ARY 選定後再改。

## 3. 誰可以用

Gmail 是公司資產工具（`tool.yaml` 沒有 `source_talent`），OMC 的 `ToolRegistry` 會給**所有員工**；
`allowed_users` 只對「員工自帶的工具」有效，所以這裡**刻意不設**。草稿寄不出去，所以全員開放是 ARY
同意的做法。以後要限制，要改後端（`ToolRegistry._is_allowed`）或把工具改成人才工具；
注意 OMC 規則是 **EA 一律可用全部工具**。

## 4. 設定（client 憑證用唯讀 secret 檔）

Client ID / Secret 不放 OMC 的 `.env`、不進 git、不進映像，跟 crawl4ai token 同樣做法：

1. ARY 依第 7 節在 Google Cloud Console 建好「電腦版應用程式」OAuth 用戶端，下載 JSON。
2. 放到 Harbor：`harbor-infra/stacks/ai/onemancompany/secrets/google_oauth_client.json`
   （目錄 700、檔案 600、owner `ary`；`secrets/` 已在 `.gitignore` 和 `.dockerignore`）。
   Google 下載的 JSON 原樣即可（`{"installed": {"client_id": …, "client_secret": …}}`）。
   **一定要在部署前先放好**：單檔 bind mount 的來源不存在時，Docker 會建立一個同名「資料夾」。
3. `compose.yaml`（`onemancompany` 服務）：
   ```yaml
   environment:
     GOOGLE_OAUTH_CLIENT_FILE: /run/secrets/google_oauth_client.json
   volumes:
     - ./secrets/google_oauth_client.json:/run/secrets/google_oauth_client.json:ro
   ```
   並把 build arg `OMC_REF` 改成含本功能的 commit。
4. 讀取順序（`core/oauth.py: resolve_client_credentials`）：`GOOGLE_OAUTH_CLIENT_FILE` 指的檔案 →
   環境變數 `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET`。用檔案時，client secret
   **不會**再抄一份進 token 快取。工具頁會顯示「Client 憑證：由 secret 檔提供」，不能在 UI 改。
5. Token 快取：OMC data volume 的 `company/assets/.oauth_cache/gmail_tokens.json`
   （在 volume 裡、不在映像；fork 的 `.gitignore` 有 `.oauth_cache/`，stack `.dockerignore` 有 `.onemancompany`）。

## 5. 遠端授權（不用開新 port）

OMC 的 OAuth callback 只在容器裡的 `localhost:8585` 聽，ARY 的瀏覽器連不到。做法是「貼網址」：

1. OMC → 工具 → **Gmail** → 按 **Login with gmail**（或員工用到 Gmail 時跳出的授權視窗按 Authorize）。
2. 在 Google 頁面選 **uzena.nari@gmail.com** → 看到「Google 尚未驗證這個應用程式」/「測試中」→ 按「繼續」
   （正式版未驗證時是「進階」→「前往 OMC Drafts（不安全）」）。
3. 權限頁兩個項目都要打勾：「查看您的電子郵件和設定」、「管理草稿及傳送電子郵件」。
   （第二個是 `gmail.compose` 的名稱；寄信功能已在程式碼裡拿掉，見第 2 節。）→ 繼續。
4. 瀏覽器會跳到 `http://localhost:8585/callback?state=…&code=…` 並顯示「無法連上這個網站」——**這是正常的**。
5. 把網址列的**完整網址**複製，貼到 Gmail 工具頁的輸入框，按 **完成授權**。
   OMC 在容器裡用 PKCE verifier 換 token（`POST /api/tools/gmail/oauth/exchange`），state 必須對上、
   只能用一次、10 分鐘內有效；回應不含 token。工具頁變成 **Connected** 就好了。
6. 測試：叫 EA「用 gmail_get_profile 告訴我帳號」→ 應該是 `uzena.nari@gmail.com`；
   再叫他「寫一封草稿給自己（uzena.nari@gmail.com），主旨『測試草稿』」→ 到 Gmail 草稿匣看，**不要**讓任何東西寄出。

## 6. 撤銷存取

1. Google 端（最徹底）：用 uzena.nari@gmail.com 開 <https://myaccount.google.com/permissions> →
   找到 **OMC Drafts** → 「刪除所有連結」/「移除存取權」。token 立刻失效。
2. OMC 端：工具頁 Gmail 按 **Disconnect**（會刪 `company/assets/.oauth_cache/gmail_tokens.json`）。
3. 要完全停用：再把 compose 的 `GOOGLE_OAUTH_CLIENT_FILE` 和掛載拿掉（King ops `up`），
   或在 Google Cloud Console 刪掉該 OAuth 用戶端。

## 7. Google Cloud Console 設定（ARY 用 uzena.nari@gmail.com 操作）

（Google 介面偶爾改名；括號是英文介面的名稱。）

1. 開 <https://console.cloud.google.com/>，右上角頭像確認是 **uzena.nari@gmail.com**（不是就切換帳號）。
   第一次使用要同意服務條款。
2. **建專案**：左上角專案選單 →「新增專案」(New project) → 專案名稱 `OMC-Gmail` → 位置維持「無機構」→
   「建立」→ 等通知出現後按「選取專案」，確認上方顯示 `OMC-Gmail`。
3. **啟用 Gmail API**：左上 ☰ →「API 和服務」(APIs & Services) →「程式庫」(Library) → 搜尋 `Gmail API` →
   點進去 →「啟用」(Enable)。
4. **OAuth 同意畫面**：☰ →「API 和服務」→「OAuth 同意畫面」（新版會帶你到「Google 驗證平台 / Google Auth Platform」）
   →「開始」(Get started)：
   - 應用程式資訊：應用程式名稱 `OMC Drafts`；使用者支援電子郵件選 `uzena.nari@gmail.com` →「下一步」
   - 目標對象 (Audience)：選 **外部** (External) →「下一步」
   - 聯絡資訊：填 `uzena.nari@gmail.com` →「下一步」
   - 勾選同意「Google API 服務：使用者資料政策」→「繼續」→「建立」
5. **測試使用者**：左邊「目標對象」(Audience) → 確認「發布狀態」是 **測試中** (Testing) →
   「測試使用者」(Test users) →「新增使用者」(Add users) → 輸入 `uzena.nari@gmail.com` →「儲存」。
6. （可省略）**資料存取**：左邊「資料存取」(Data Access) →「新增或移除範圍」→ 在「手動新增範圍」貼上
   `https://www.googleapis.com/auth/gmail.readonly` 和 `https://www.googleapis.com/auth/gmail.compose`
   →「加入表格」→「更新」→「儲存」。OMC 授權時本來就會要求這兩個範圍，這步只是讓畫面上有紀錄。
7. **建立 OAuth 用戶端**：左邊「用戶端」(Clients) →「建立用戶端」(Create client) →
   應用程式類型選 **電腦版應用程式** (Desktop app) → 名稱 `OMC Harbor` →「建立」。
   出現的視窗按 **「下載 JSON」**（Google 現在只在建立當下顯示完整密鑰，錯過就要重建或新增一組密鑰）。
   電腦版用戶端**不用**設定重新導向 URI（Google 允許 loopback `http://localhost:<port>`）。
8. 把下載的 `client_secret_….json` 交給我放到 Harbor 的 `secrets/google_oauth_client.json`
   （不要貼到聊天、不要 email；檔案留在電腦裡跟我說路徑即可）。

**「測試中」的 refresh token 7 天就過期**（Gmail 範圍不在豁免名單）。選項：

| 做法 | 好處 | 代價 |
|---|---|---|
| A. 維持「測試中」，每 7 天照第 5 節重新授權 | 只有測試使用者能授權；最保守 | 每週要重做一次（約 1 分鐘），過期期間員工讀不到信、寫不了草稿 |
| B. 按「發布應用程式」改「正式版」、不送驗證（建議先 A 測通再改 B） | token 不會 7 天過期（除非 6 個月沒用、改密碼或撤銷） | 授權時會看到「未驗證」警告要按進階；未驗證 app 終身最多 100 位使用者；任何 Google 帳號理論上都能授權這個 app（但只會開放他們自己的信箱，OMC 也會拒絕非 uzena.nari 的帳號）；**發布後要重新授權一次** |
| C. 送 Google 驗證 | 沒有警告 | Gmail 是受限範圍，要做安全評估（CASA），費時可能要付費，個人用不值得 |
| D. Workspace「內部」 | 不過期、不用驗證 | 只適用 Google Workspace 組織帳號；uzena.nari@gmail.com 是個人帳號，不適用 |

## 8. 部署與回滾

部署（要 ARY 同意，經 King ops）：

1. 先備份：`docker tag harbor-onemancompany:0.7.113-3fde188 harbor-onemancompany:rollback-pre-gmail-20261028`；
   `compose.yaml` 備份為 `compose.yaml.bak-<UTC時間>-gmail`；data volume 的 gmail 原檔備份在 Harbor
   `~/omc-backups/gmail-drafts-only-*/original/`。
2. 放好 `secrets/google_oauth_client.json`（600）。
3. 把 `gmail.py`、`mcp_server.py`、`tool.yaml`、`shared_prompts/tool_usage.md` 複製進 data volume
   （entrypoint 只在第一次建立 company/，重建映像**不會**更新 volume 裡的工具）。
4. 套用 compose 改動（`OMC_REF` + 環境變數 + 掛載）→ `APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up --build`
   （約 2–3 分鐘建置期間舊版照常跑，實際停機約 30 秒）。
5. 照第 5 節授權、測試。

只改 data volume 的工具檔（第 3 步）、不重建：OMC 自己的 graceful restart
（`POST /api/admin/apply-code-update`，約 5 秒）就會重新載入 `gmail.py`；`mcp_server.py` 下次員工開
Claude CLI 時就生效。但**遠端授權和 secret 檔讀取在 `core/oauth.py`／`routes.py`／`frontend/app.js`，
一定要重建映像**。

回滾：

```bash
# Harbor：harbor-infra/stacks/ai/onemancompany
cp compose.yaml.bak-<UTC時間>-gmail compose.yaml
docker tag harbor-onemancompany:rollback-pre-gmail-20261028 harbor-onemancompany:0.7.113-3fde188
APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up      # 不加 --build
# data volume 的工具檔：把 ~/omc-backups/gmail-drafts-only-*/original/ 的檔案 docker cp 回
#   /workspace/.onemancompany/company/assets/tools/gmail/ 與 company/shared_prompts/，再 apply-code-update（約 5 秒）
```

注意：回滾工具檔會把 `gmail_send`／`gmail_reply` 加回來。程式碼回滾：`git revert <本次 commit>`。

## 相關檔案

- `company/assets/tools/gmail/gmail.py`、`mcp_server.py`、`tool.yaml`
- `src/onemancompany/core/oauth.py`（`client_file_env`、`resolve_client_credentials`、`complete_oauth_from_redirect`）
- `src/onemancompany/api/routes.py`（`POST /api/tools/{tool_id}/oauth/exchange`、secret 檔偵測）
- `frontend/app.js`（工具頁 OAuth 區塊：貼網址欄位、「由 secret 檔提供」）
- `company/shared_prompts/tool_usage.md`、`company/assets/tools/README.md`
- `tests/unit/test_gmail_drafts_only.py`
