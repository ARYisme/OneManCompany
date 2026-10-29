# 企劃人才包（ary-product-planner）設計說明

建立：2026-10-29（AEDT）。本地人才包，位置 `src/onemancompany/talent_market/talents/ary-product-planner/`。

## 重點

| 項目 | 設定 |
|---|---|
| 中文職稱 | 企劃 |
| 模型 | `foundry-gx10-main` |
| role | `Planner` → 對不到 `ROLE_DEPARTMENT_MAP` → 部門 General → `DEFAULT_TOOL_PERMISSIONS` 為空，**沒有 bash** |
| 工具 | web_search（全員有）、web_fetch（manifest `custom_tools`，onboarding 加入 allowed_users）、檔案讀寫、專案／任務／協作工具（全員基本工具）、gmail（公司共用，只能寫草稿） |
| Skills | product-service-plan、market-entry、project-roadmap、proposal-writing、cost-benefit |
| 合作 | 市場研究員 00006（市場數據、競品、價格） |
| 規則 | 繁中；數字附來源與日期；不編造；沒工具就說做不到、不謊報完成；不寫程式繞過限制；Email 只存草稿 |

注意：`skills/` 被上層 `.gitignore` 規則擋住，提交時要 `git add -f`（同 38f8e27）。

## 社群做法參考（2026-10-29 查詢）

| 來源 | 借用了什麼 |
|---|---|
| MetaGPT ProductManager（[role](https://github.com/FoundationAgents/MetaGPT/blob/11cdf466/metagpt/roles/product_manager.py)、[WritePRD prompt](https://bitfreedom.net/code/apunkt/MetaGPT/raw/commit/e315d8365b1d117659938932e0b72f645f37394b/metagpt/actions/write_prd.py)、[PM 指令](https://bitfreedom.net/code/apunkt/MetaGPT/commit/29af174ef12b0b433a8659201b6ead90d4158c49)） | PRD 欄位：改寫原始需求、≤3 個正交目標、3–5 則使用者故事、5–7 家競品、P0/P1/P2 需求池、不清楚事項；「需求簡單就簡單寫」；語言跟隨使用者；先搜尋再寫 |
| agency-agents Sprint Prioritizer（[檔案](https://github.com/msitarzewski/agency-agents/blob/main/product/product-sprint-prioritizer.md)、[playbook](https://github.com/msitarzewski/agency-agents/blob/main/strategy/playbooks/phase-1-strategy.md)） | RICE（影響 0.25–3、工作量人月）、MoSCoW、Kano、價值／工作量矩陣、相依與關鍵路徑、里程碑；工具只用 WebFetch／WebSearch／Read／Write／Edit（無 shell） |
| CrewAI（[Crafting Effective Agents](https://docs.crewai.com/v1.11.0/en/guides/agents/crafting-effective-agents)、[PM 範例](https://github.com/CharlieChenyuZhang/crewai-pm-deepresearch/blob/main/pm.py)、[Product Planner 範本](https://pages.edgeone.ai/templates/crewai-product-planner-starter)） | 80/20：重點放在任務與交件格式；PRD 要有驗收條件、時程、風險、引用來源；先問 2–3 輪選擇題再起草 |
| ChatDev CPO（[RoleConfig](https://github.com/yhyu13/ChatDev/commit/6434cbb5fdd8763b9e4276dc8b389e669cdb5b1a)） | 職責範圍：產品設計、策略、願景、創新、專案管理、產品行銷 |
| OMC Talent Market「Product Manager Skills」（[頁面](https://one-man-company.com/talent/product-manager-skills)）與 [deanpeters/Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)（[prd-development](https://github.com/deanpeters/Product-Manager-Skills/blob/main/skills/prd-development/SKILL.md)、[user-story](https://github.com/deanpeters/product-manager-skills/blob/main/skills/user-story/SKILL.md)） | 官方市集的 PM 人才是「skills 集合」形式；使用者故事＋驗收條件 |
| OMC 官方文件（[Hiring](https://1mancompany.github.io/OneManCompany/docs/guide/hiring/)、[Publish to Talent Market](https://1mancompany.github.io/OneManCompany/docs/guide/publish-to-talent-market/)） | 人才包結構：profile.yaml、DESCRIPTION.md、skills/*/SKILL.md、tools/ |

AutoGen：沒有找到專門的 PM 角色範本，未採用。

## 和社群版本的差異（刻意）
- 不做軟體技術規格（MetaGPT 預設 React 技術棧）——老闆的事業是食品／零售，改成 4P、通路、AUD 成本效益。
- 沒有 bash、不寫程式：成本計算手算並寫出算式，方便老闆驗算。
- 對外只存 Gmail 草稿（見 email-drafts-only.md）。
