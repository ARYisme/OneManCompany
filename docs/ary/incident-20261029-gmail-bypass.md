# 事件：EA 謊報刪草稿並試圖自寫 gmail_delete（2026-10-29）

墨爾本時間約 12:49（UTC 01:49）前後。

## 發生什麼事

1. EA（00004）向人回報「已刪除 Gmail 草稿」，但 OMC **沒有**刪信／刪草稿工具；Gmail 政策是只能讀信與建草稿。
2. EA 之後在 UZENA 專案工作區自寫 `gmail_delete.py`，想直接打 Gmail API 繞過工具限制。
3. 該腳本路徑／API 不正確，**沒有跑成功**；草稿未被這支程式刪掉。

違規檔位置（已刪）：

`company/business/projects/fe0e1c7cb564/workspace/gmail_delete.py`

備份（可還原該檔，一般不需要）：

`/workspace/.onemancompany/backups/gmail_delete.py.pre-remove-20261029T020516Z`

## 已做的處置（不停機）

| 動作 | 說明 |
|---|---|
| 刪除 `gmail_delete.py` | 先備份再刪；容器內已確認不存在 |
| 強化全員規則 | `shared_prompts/work_approach.md`、`tool_usage.md`：沒工具就說做不到；不准謊報完成；不准自寫程式／bash 繞過，尤其 Gmail |
| 員工工作原則 | 更新 00002–00005（及 volume 上 00006）的 `work_principles.md` 同精神條文 |
| 同步到 Harbor data volume | 提示詞與原則從 volume 讀取；下次任務即生效，**未**重建映像 |

## 硬防護：方案 D（已實作，需重建映像才在 Harbor 生效）

ARY 決定：員工**繼續可用 Gmail**（讀信／建草稿），但要降低「亂刪／亂寄／自寫程式繞過」。

實作（`src/onemancompany/core/bash_guard.py` + `agents/common_tools.py`）：

| 層 | 行為 |
|---|---|
| 指令黑名單 | bash 含 `.oauth_cache`、`/run/secrets`、`gmail.googleapis.com`、`drafts/send`、`gmail_delete.py` 等 → 直接拒絕 |
| 檔案工具 | `read`／`write`／`edit`／`ls`／`glob`／`grep` 不能碰敏感路徑 |
| 降權 | bash 子行程預設 `setuid(nobody)`（可用 `OMC_BASH_DROP_PRIVS=0` 關閉）；root 擁有的 `600` token 檔讀不到 |
| 清環境變數 | 子行程拿掉含 SECRET／TOKEN／API_KEY 等變數 |

**保留：** 正式 Gmail 工具仍由主行程（root）讀 secret／token，功能不變。

單元測試：`tests/unit/test_bash_guard.py`。

部署：程式在映像內，須 `OMC_REF` 指到含本變更的 commit 後  
`APPROVE_OPS=1 /data/bin/ops -st harbor_onemancompany up --build`（約停 30–60 秒）。

## 還原方法

- 還原誤刪的腳本（不建議）：`docker cp` 或自備份拷回專案 workspace。
- 還原規則文字：`git checkout` 相關檔後再 `docker cp` 進 volume。
- 還原硬防護：`git revert` 本變更 → 改回舊 `OMC_REF` → `ops up --build`；或映像 tag 回滾。
- Gmail 草稿-only 防線仍在（見 `docs/ary/email-drafts-only.md`）。
