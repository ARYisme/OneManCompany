# 權限中心（Permission Center）

時間：2026-10-30（AEDT）。不含 secret。

## 一句話

獨立頁面管理「部門預設 × 危險工具」矩陣，可對個別員工設例外（允許／拒絕），**拒絕優先**；每次變更寫稽核，存檔後立即生效，不用重啟 OMC。

## 行為

| 項目 | 說明 |
|---|---|
| 入口 | 工具列鎖頭按鈕「Permission Center」；職員概覽也會連過來（職員分頁任務） |
| 部門預設 | 寫入 `company/human_resource/tool_permissions.yaml`；聘用／未設例外的員工依部門生效 |
| 員工例外 | 寫入該員工 `profile.yaml` 的 `tool_permissions`；**有這個欄位（含 `[]`）就整份取代部門預設** |
| 拒絕優先 | 例外清單裡的 `!bash` 或 `-bash` 會蓋掉允許 |
| 熱生效 | `execute_tool`／下次任務 `_refresh_agent` 會重抓工具列表；存檔時也嘗試刷新記憶體中的 agent |
| 稽核 | journal `permission_changed`／`permission_denied`＋ activity_log |
| 管哪些工具 | bash、use_tool、預算／cron／webhook／背景任務、`request_api_key` 等 gated（見 D-01） |
| 不管 | `web_fetch` 仍走 talent `allowed_users` 白名單；base 工具（讀寫檔等）全員可用 |

## API

| 方法 | 路徑 | 作用 |
|---|---|---|
| GET | `/api/permissions` | 矩陣＋員工例外＋近期稽核 |
| PUT | `/api/permissions/departments` | 存部門預設 `{departments, actor_id}` |
| PUT | `/api/permissions/employee/{id}` | 設例外 `{tool_permissions, actor_id}` |
| DELETE | `/api/permissions/employee/{id}` | 清除例外，改跟部門 |

## 與 D-01 的關係

D-01 修好「gated 預設拒絕」後，本頁才是日常開關 bash／tools 的地方。未部署前 Harbor 上改這裡不會生效。

## 測試

- `tests/unit/core/test_permissions.py`
- `tests/unit/api/test_permissions_routes.py`
- 既有 `test_tool_registry.py`（含拒絕優先）

## 回滾

`git revert` 本 commit；可手動刪 volume 內 `tool_permissions.yaml`（會回到程式內建部門預設）。
