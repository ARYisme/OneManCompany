# 部署紀錄：白話能力開關權限中心 2026-10-30

時間 AEDT。不含 secret。

| 項目 | 值 |
|---|---|
| Commit | `9bf7c5f`（已 push `ary-readable-ui`） |
| 映像 | `harbor-onemancompany:0.7.113-9bf7c5f` |
| 窗口 | 01:15:41Z 開始 `up --build` → 01:18:11Z Started（AEDT 12:15–12:18） |
| 停機 | 切換約 **15–20 秒**（build 期間舊容器仍服務；Recreate→Started） |
| 回滾 | `harbor-onemancompany:rollback-pre-capui-20261030T011519`（= `0.7.113-ff71395`） |
| 資料備份 | `omc-data-pre-capui-rebuild-20261030T011519.tgz` |
| 設定備份 | `*.bak-20261030T011519-pre-capui` |

## 權限不變性（五員工）

部署前後 `tool_permissions` key 有無、內容、與 soft `permissions` 皆 **MATCH**：

| ID | 角色 | tool_permissions |
|---|---|---|
| 00002 | HR | （無 key） |
| 00003 | COO | `[use_tool]` |
| 00004 | EA | `[bash, use_tool]` |
| 00005 | CSO | （無 key） |
| 00006 | Analyst | `[]` |

## 畫面

- 主畫面能力開關：`docs/ary/screenshots/perm-center-main-9bf7c5f.png`
- 展開進階設定：`docs/ary/screenshots/perm-center-advanced-9bf7c5f.png`

（截圖用部署映像同版前端 + 容器內 live `/api/permissions` 資料；Harbor 登入層自動化無法直連時之等效實畫面。）

## 回滾

還原 compose／.env 的 `*.bak-20261030T011519-pre-capui`，或把映像指回 rollback tag，再：

`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up`（不加 `--build`）
