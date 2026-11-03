# 部署紀錄：恢復文件下載 + 路由陰影修復 2026-11-03

時間 AEDT。不含 secret。

| 項目 | 值 |
|---|---|
| Commit | `b2df6a5`（已 push `ary-readable-ui`） |
| 映像 | `harbor-onemancompany:0.7.113-b2df6a5` |
| 窗口 | 10:13 → 10:15 AEDT（`up --build` ≈ 131s；切換停機約 15–20 秒） |
| 停機 | 切換約 **15–20 秒**（build 期間舊容器仍服務） |
| 回滾 | `harbor-onemancompany:rollback-pre-download-20261103T021306`（= `0.7.113-0045d9d`） |
| 資料備份 | `omc-data-pre-download-rebuild-20261103T021306.tgz` |
| 設定備份 | `*.bak-20261103T021306-pre-download` |

## 題詞

恢復專案／產品內容「下載」；修復 `{iteration_id}`／`{sprint_id}` 蓋住靜態路徑。

## 驗證

- 容器 `healthy`；映像 `0.7.113-b2df6a5`
- Product `豆芽菜機器中間商`：`/ls` 見 `negotiation-playbook.md`
- `GET .../files/negotiation-playbook.md` 與磁碟 **26502 bytes**，SHA256 `9e30582b5e92a81692dac191e8bf3cc24099cdbaee2cd441e85ad937f033aa60`，MATCH
- 專案 `e3f236c474e4`：`/ls` 200、`/download` ZIP 可用
- 截圖：`docs/ary/screenshots/download-verify-b2df6a5.png`（登入層擋住自動化瀏覽器時之等效實畫面）

## 回滾

還原 compose／.env 的 `*.bak-20261103T021306-pre-download`，或映像指回 rollback tag，再：

`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up`（不加 `--build`）
