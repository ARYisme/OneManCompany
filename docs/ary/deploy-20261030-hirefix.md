# 部署紀錄：本地人才 batch-hire 修復 2026-10-30

時間 AEDT。不含 secret。

| 項目 | 值 |
|---|---|
| Commit | `568a4cf`（已 push） |
| 映像 | `harbor-onemancompany:0.7.113-568a4cf` |
| 窗口 | 02:48:02Z → 02:50:31Z Started（AEDT 13:48–13:50） |
| 停機 | 切換約 **15–20 秒** |
| 回滾 | `harbor-onemancompany:rollback-pre-hirefix-20261030T024752`（= `0.7.113-eb76e88`） |
| 資料備份 | `omc-data-pre-hirefix-rebuild-20261030T024752.tgz` |

## 驗證

- 本地包跳過雲端購買：`Skipping Talent Market purchase for local package ary-product-planner`
- Smoke `batch-hire` → `status=onboarding`（不再 `Talent … not found`）
- 背景錄用成功：`1 hired, 0 failed` → 員工 **00007 企劃**
