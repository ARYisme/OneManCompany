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

## 尚未改的硬防護（等 ARY 選方案）

提示詞只能降低機率，擋不住有 `bash` 的員工讀 token 或自打 API。  
容器目前以 root 跑，`.oauth_cache/gmail_tokens.json` 雖是 `600`，對 root 的 bash **無效**。

可選方案見同日回報給 ARY 的表格（鎖 token 路徑／降權跑 bash／收回 bash／擋 Gmail API 出口等）。**未獲同意前不實作、不停機。**

## 還原方法

- 還原誤刪的腳本（不建議）：`docker cp` 或自備份拷回專案 workspace。
- 還原規則文字：`git checkout` 相關檔後再 `docker cp` 進 volume。
- Gmail 工具本身未改；草稿-only 程式防線仍在（見 `docs/ary/email-drafts-only.md`）。
