# 權限中心（Permission Center）

時間：2026-10-30（AEDT）。不含 secret。

## 一句話

左側邊欄固定「權限中心」入口；部門×工具、員工例外都是**三段開關**（允許／拒絕／繼承），按儲存後有成功提示，立即生效。

## 入口（所有登入者都看得到）

| 位置 | 說明 |
|---|---|
| **左側邊欄最上** | 綠色框按鈕「🔒 權限中心」（主要入口，固定可見） |
| 頂部狀態列 | 鎖頭＋「權限」小字（次要；窄螢幕可能要橫滑） |
| 職員詳情 → 概覽 | 「到權限中心管理」（該頁本身是**唯讀**標籤，不能改） |

沒有另設帳號權限：只要能開 OMC 後台，就能開權限中心。

## 三段開關

點格子循環：**允許 → 拒絕 → 繼承 → 允許**

| 狀態 | 部門矩陣意義 | 員工例外意義 |
|---|---|---|
| 允許 | 此部門明確給此工具 | 此員工明確給 |
| 拒絕 | 此部門明確不給（`!tool`） | 此員工明確不給（拒絕優先） |
| 繼承 | 跟程式內建部門預設 | 跟該員工所屬部門的生效結果 |

- 員工若「全部繼承」再儲存 → 會清除例外（跟部門）。
- 舊的空白例外 `tool_permissions: []`（如 00006）仍視為**全部拒絕**（相容）。

## 儲存

- 「儲存部門預設」「儲存員工例外」：成功會跳出綠色 toast。
- 寫入 `company/human_resource/tool_permissions.yaml`（version 2）或員工 `profile.yaml`；不用重啟。

## API

| 方法 | 路徑 | 作用 |
|---|---|---|
| GET | `/api/permissions` | 含 `department_states`／`tool_states`（allow\|deny\|inherit） |
| PUT | `/api/permissions/departments` | 存部門 token（可含 `!tool`） |
| PUT | `/api/permissions/employee/{id}` | 設例外 |
| DELETE | `/api/permissions/employee/{id}` | 清除例外 |

## 測試

- `tests/unit/core/test_permissions.py`
- `tests/unit/api/test_permissions_routes.py`
- `tests/frontend/test_permission_center_ui.js`
