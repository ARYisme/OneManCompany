# 職員詳情四分頁

時間：2026-10-30（AEDT）。不含 secret。

## 一句話

職員詳細頁太擠，改成四個分頁：**概覽／任務／紀錄／調教**；概覽只顯示唯讀工具權限標籤，改權限請到權限中心。

## 分頁內容

| 分頁 | 內容 |
|---|---|
| 概覽 | 頭像、基本資料、能力 Perms 標籤、績效、OKR、模型設定、**工具權限唯讀標籤**、連到權限中心、解雇 |
| 任務 | Task Board、Scheduled Jobs |
| 紀錄 | Execution Log、Work History、Project History |
| 調教 | Start 1-on-1、Work Principles、1-on-1 Notes（原本功能保留） |

## 行為

- 開職員詳情預設落在「概覽」。
- 工具權限標籤從 `GET /api/employee/{id}` 的 `effective_tool_permissions` 讀取，**不能在此頁勾選修改**。
- 「到權限中心管理」會關掉職員詳情並打開 Permission Center，並預選該員工。
- 1-on-1 按鈕仍在「調教」分頁，行為與以前相同。

## 測試

- `tests/frontend/test_employee_detail_tabs.js`
- 權限欄位與 Permission Center／D-01 單元測試一併涵蓋後端

## 回滾

`git revert` 本 commit。
