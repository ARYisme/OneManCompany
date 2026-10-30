# 部署紀錄：繼承生效顯示＋鎖頭去字 2026-10-30

時間 AEDT。不含 secret。不改員工實際權限。

| 項目 | 值 |
|---|---|
| Commit | `eb76e88`（已 push） |
| 映像 | `harbor-onemancompany:0.7.113-eb76e88` |
| 窗口 | 01:30:24Z 開始 → 01:32:50Z Started（AEDT 12:30–12:33） |
| 停機 | 切換約 **15–20 秒** |
| 回滾 | `harbor-onemancompany:rollback-pre-inheritui-20261030T013006`（= `0.7.113-9bf7c5f`） |
| 資料備份 | `omc-data-pre-inheritui-rebuild-20261030T013006.tgz` |
| 設定備份 | `*.bak-20261030T013006-pre-inheritui` |

## 驗證

- 五員工 `tool_permissions`／`permissions` 與部署前 **ALL_MATCH**。
- Snapshot 含 `code_defaults`；Engineering 內建含 `bash`+`use_tool`。
