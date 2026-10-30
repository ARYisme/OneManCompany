# D-01：bash／危險工具改為明確授權（預設拒絕）

時間：2026-10-30（AEDT，UTC+11）。不含任何 secret。

## 一句話

改職稱或清空 `tool_permissions` **本來擋不住 bash**——因為 bash 被註冊成 `base`，且權限檢查對 `base`／`gated` 一律放行。現已改成：危險工具屬 `gated`、沒有明確授權就拒絕，並寫稽核紀錄。

## 修改前實測（Harbor 現況映像 `0.7.113-4e2eddc`）

| 員工 | role / 部門 | `tool_permissions` | 能否拿到 bash |
|---|---|---|---|
| 00006 花满 | Analyst / Analytics | `[]` | **能**（bug） |
| 00004 EA | EA / CEO Office | （profile 未設） | 能 |
| 00003 COO | COO / Operations | （profile 未設） | 能 |
| 00002 HR、00005 CSO | … | （profile 未設） | 能 |

容器內驗證：`bash` 的 `category=base`，`gated tools: []`；00006 與其他人 `tool_count` 相同且 `bash_in_tools=True`。

根因：

1. `common_tools._register_all_internal_tools` 把 bash、`use_tool`、cron、webhook、背景任務、`request_api_key` 等註冊成 **base**（註解寫「Formerly gated」）。
2. `ToolRegistry._is_allowed` 對 `base` **與** `gated` 都直接 `return True`；文件寫的「gated 要看 tool_permissions」沒有實作。
3. 舊測試 `test_gated_tools_always_included` 還在鎖定這個錯誤行為。

`web_fetch` 仍走 talent asset 白名單（`allowed_users`），此修不改它。5998b66 的 nobody／Gmail／secret bash_guard 也不動。

## 行為變更（部署後才會在 Harbor 生效）

| 項目 | 之前 | 之後 |
|---|---|---|
| bash、`use_tool`、預算／cron／webhook／背景任務／`request_api_key` 等 | 全員可用（base） | **gated**：要在該員工 `tool_permissions` 裡明確寫工具名 |
| 預設 | 放行 | **拒絕**（沒寫 = 不能用） |
| 拒絕優先 | 無 | `tool_permissions` 含 `!bash` 或 `-bash` 時，即使同時有 `bash` 也拒絕 |
| EA 角色特權 | 所有工具（含危險）一律放行 | **不再繞過 gated**；base／role／asset 仍可走 EA 特權 |
| 執行路徑 | 只靠「工具列表過濾」 | `execute_tool()` 再檢查一次；拒絕時寫 journal（`permission_denied`）＋ activity_log |
| web_fetch | talent 白名單 | **維持** |

部門聘用預設（未改邏輯，只是終於會生效）：

- Engineering／Design／Analytics／Marketing → `["bash", "use_tool"]`
- General 及其他 → `[]`

## 部署後建議補授權（請 ARY 決定，此 commit 不改 live 員工資料）

| 員工 | 建議 | 原因 |
|---|---|---|
| 00004 EA | 若仍要下指令／用設備：補 `bash`、`use_tool`（必要時再加 cron／notify 等） | 部署後會失去所有 gated |
| 00003 COO | 若要管自動化或授權工具：視需要補 `bash`／`use_tool`／相關 gated；COO 仍可用 `manage_tool_access` 幫別人授權（該工具本身若未註冊進列表則另議） | profile 沒有 tool_permissions |
| 00002 HR、00005 CSO | 通常 **不必** bash；維持空即可 | 業務不需 shell |
| 00006 花满 | **維持 `[]`** | 人才包 v2 刻意拿掉 bash；web_fetch 白名單保留 |

補授權方式（部署並同意後）：COO 工具 `manage_tool_access`，或直接改 `employees/{id}/profile.yaml` 的 `tool_permissions`（熱重載讀檔）。後續「權限中心」頁會統一管理。

## 測試

- 新增／修正：`tests/unit/core/test_tool_registry.py`
  - 沒授權拿不到 bash；有授權拿得到；`!bash` 拒絕優先
  - 00006 風格 `[]` 拿不到 bash
  - `execute_tool` 拒絕並呼叫稽核；有授權可執行
- 修改前（僅新測試）：3 failed（符合預期紅燈）
- 修改後：`uv run pytest tests/unit/core/test_tool_registry.py` → **40 passed**

## 回滾

`git revert` 本 commit 後依 Harbor 流程重建映像即可；員工 profile 未被本變更改寫。
