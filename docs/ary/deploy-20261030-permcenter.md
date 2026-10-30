# 部署紀錄：權限中心／D-01／職員分頁（2026-10-30）

時間一律 AEDT（UTC+11）。不含 secret。

## 結果

| 項目 | 值 |
|---|---|
| 分支／commits | `ary-readable-ui`：`373945a` → `59c4757` → `b0a0c5c`（已 push） |
| 映像 | `harbor-onemancompany:0.7.113-b0a0c5c`（容器 healthy） |
| 部署窗口 | 11:39:14 開始 build → 11:41:45 新容器 Started（約 2.5 分鐘） |
| 實際停機 | 切換當下約 **15–20 秒**（build 期間舊容器持續服務） |
| 回滾映像 | `harbor-onemancompany:rollback-pre-permcenter-20261030T003846`（= `0.7.113-4e2eddc`） |
| 資料備份 | `/workspace/.onemancompany/backups/omc-data-pre-permcenter-rebuild-20261030T003846.tgz` |
| 設定備份 | Harbor stack：`compose.yaml`／`.env`／`.env.example` 的 `.bak-20261030T003846-pre-permcenter` |

## 部署後授權

| 員工 | 變更 |
|---|---|
| 00004 EA | `tool_permissions: [bash, use_tool]` |
| 00003 COO | `tool_permissions: [use_tool]` |
| 00002 HR、00005 CSO、00006 | 不變（00006 仍 `[]`） |

## 驗證

- 5 位員工皆 `idle`；bash 類別為 `gated`。
- EA `execute_tool(bash)` → `status=ok`，stdout `ea-bash-ok`。
- 00006 `execute_tool(bash)` → `status=denied`；activity `permission_denied`＋ journal `permission_denied` 各有紀錄。

## 回滾

在 Harbor stack 目錄以 `cp -p` 還原三個 `.bak-20261030T003846-pre-permcenter`，aunode 跑  
`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up`（不加 `--build`）。  
員工授權若要一併還原，從資料備份 tgz 還 profile，或權限中心清例外。
