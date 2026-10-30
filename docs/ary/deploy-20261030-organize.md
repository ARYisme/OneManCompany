# 部署紀錄：Projects 未歸類整理 2026-10-30

時間 AEDT。不含 secret。

| 項目 | 值 |
|---|---|
| Commit | `97c22b7`（已 push `ary-readable-ui`） |
| 映像 | `harbor-onemancompany:0.7.113-97c22b7` |
| 窗口 | 18:57:31 → 18:59:50 Started（AEDT） |
| 停機 | 切換約 **15–20 秒**（build 期間舊容器仍服務） |
| 回滾 | `harbor-onemancompany:rollback-pre-organize-20261030T075704`（= `0.7.113-568a4cf`） |
| 資料備份 | `omc-data-pre-organize-rebuild-20261030T075704.tgz` |
| 設定備份 | `*.bak-20261030T075704-pre-organize` |

## 題詞

Projects 未歸類整理：批次歸入 Product／批次封存（含詳情單筆改 Product）

## 驗證

- 容器 `healthy`／`running`；映像 `0.7.113-97c22b7`
- 前端含 `_organizeSelectedProjects`／`/api/projects/organize`／整理按鈕
- API：`PATCH /api/projects/{id}/product`（缺專案 → 404）、`POST /api/projects/organize`（空列表 → 400）
- `/api/products/panel` 可回 products／orphan_projects（部署當下約 1 product、3 orphans）

## 回滾

還原 compose／.env 的 `*.bak-20261030T075704-pre-organize`，或把映像指回 rollback tag，再：

`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up`（不加 `--build`）
