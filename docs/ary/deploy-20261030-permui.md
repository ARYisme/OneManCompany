# 部署紀錄：權限中心 UI（側欄＋三段開關）2026-10-30

時間 AEDT。不含 secret。

| 項目 | 值 |
|---|---|
| Commit | `ff71395`（已 push） |
| 映像 | `harbor-onemancompany:0.7.113-ff71395` |
| 窗口 | 11:54:06 開始 build → 11:56:35 Started |
| 停機 | 切換約 **15–20 秒** |
| 回滾 | `harbor-onemancompany:rollback-pre-permui-20261030T005352`（= `0.7.113-b0a0c5c`） |
| 資料備份 | `omc-data-pre-permui-rebuild-20261030T005352.tgz` |
| 設定備份 | `*.bak-20261030T005352-pre-permui` |

## 驗證

- 側欄／標題含「權限中心」；三段循環與儲存 toast 字串在映像內。
- API `department_states` 為 allow｜deny｜inherit；儲存部門預設 OK。
- 員工 `tool_permissions` 與部署前快照一致（00004 bash+use_tool、00003 use_tool、00006 []、HR/CSO 無 key）。
