# 權限中心（Permission Center）— 白話能力開關

時間：2026-10-30（AEDT）。不含 secret。僅 `ary-readable-ui` 顯示／操作層；**不自動改寫既有員工權限資料**。

## 一句話

主畫面改成「能力開關」（白話名稱＋說明＋綠／黃／紅風險），三段：開／關／跟部門一樣；技術矩陣收進預設收合的「進階設定」。

## 入口

| 位置 | 說明 |
|---|---|
| **左側邊欄最上** | 「🔒 權限中心」 |
| 頂部狀態列 | 鎖頭＋「權限」 |
| 職員詳情 → 概覽 | 唯讀「能力」標籤（同白話名稱）＋連到權限中心 |

## 能力對照

| 白話 | 風險 | 底層 |
|---|---|---|
| 上網查資料 | 綠 | profile `web_search` |
| 讀取指定網頁 | 綠 | `web_fetch` allowed_users |
| 讀寫公司文件 | 黃 | profile `company_file_access` |
| 寫 Email 草稿 | 黃 | 顯示用（不能寄出；不可由此開關改） |
| 使用公司工具和設備 | 黃 | gated `use_tool` |
| 排程與定時工作 | 黃 | cron／webhook 類 gated |
| 發通知 | 黃 | notify／report gated |
| 在電腦上執行指令 | 紅 | gated `bash`（開啟需確認） |
| 其他 | 黃 | 其餘 gated 工具 |

## 一鍵預設

- **一般員工**／**研究員**／**技術員**：只改畫面上的草稿，按「儲存能力設定」才寫入。
- 紅色能力開啟（含技術員預設）會跳出確認。

## 進階設定

`<details>` 預設收合：部門×工具三段、員工技術例外、稽核。

- 繼承格顯示**最終結果**：`繼承（允許）`／`繼承（不給）`；明確允許／拒絕加粗加框。
- hover 說明來源（程式內建預設／員工例外覆蓋）。
- 「顯示內建預設」列出各部門 code default。
- 員工例外區三欄：部門給的｜員工例外｜最終結果。
- 白話「跟部門一樣」附帶目前部門開／關。

## 工具列／側欄

- 頂部鎖頭：**僅 🔒**，title＝權限中心。
- 側欄「🔒 權限中心」保留文字，樣式縮小。


## API

| 方法 | 路徑 | 作用 |
|---|---|---|
| GET | `/api/permissions` | 含 `capabilities`、`presets`、`capability_states`＋原矩陣 |
| PUT | `/api/permissions/employee/{id}` | body `capability_states`（白話）或 `tool_permissions`（進階） |
| PUT | `/api/permissions/departments` | 部門預設 |
| DELETE | `/api/permissions/employee/{id}` | 清除例外 |
| GET | `/api/employee/{id}` | 含 `capability_labels`（白話唯讀標籤） |

## 不變性

部署此 UI **不會**遷移或覆寫現有 `tool_permissions`／部門 YAML；只有操作者按儲存才變更該員工。

## 測試

- `tests/unit/core/test_capability_catalog.py`
- `tests/unit/core/test_permissions.py`
- `tests/unit/api/test_permissions_routes.py`
- `tests/frontend/test_permission_center_ui.js`

## UI 說明（截圖替代）

主畫面由上而下：

1. 員工下拉＋「全部改跟部門一樣」
2. 三個預設按鈕（一般員工／研究員／技術員）
3. 能力列：名稱、一句說明、風險色條、開／關／跟部門一樣
4. 「儲存能力設定」
5. 收合的「進階設定（技術矩陣）」→ 展開後才見部門表與技術工具名
