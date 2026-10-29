# ary-* 人才包 v2 補強（2026-10-29）

依 `ary-product-planner`（企劃）的標準，補強其他 6 個本地人才包。只改人才包（模板），模型維持原樣。

## 共同規則（寫進每個 system_prompt）
繁中（台灣用語）；數據附來源與查詢日期、不准編造；沒工具／權限就說做不到、不准謊報完成，交件列「做了／沒做到」；
不准寫程式或用任何方法繞過工具限制；Email 只建 Gmail 草稿；不碰機密；交件前跑品質檢查清單。

## 變更總表

| 人才包 | 模型（維持） | role v1 → v2 | bash | web_fetch | 新增 skill | 其他 |
|---|---|---|---|---|---|---|
| ary-coder 程式工程師 | foundry-gx10-main | Engineer → Engineer | 保留（受 5998b66 bash_guard：nobody、擋 Gmail／secret） | 新增 | safe-change-sop | review 分級 🔴🟡💭；「沒跑過不能說測過」 |
| ary-copywriter 文案 | foundry-gx10-fast | Marketing → Copywriter | 拿掉 | 新增 | claims-check | ACCC 宣稱、Spam Act 檢查 |
| ary-market-researcher 市場研究員 | foundry-gx10-main | Analyst → Market Researcher | 拿掉 | 保留（本包自帶） | trend-scan | ≥3 組關鍵字、≥2 來源、信心程度 |
| ary-secretary 秘書 | foundry-gx10-fast | Assistant → Assistant | 本來就沒有 | 不給 | exec-summary | SCQA 摘要、不加原文沒有的事實 |
| ary-tw-stock 台股研究員 | foundry-gx10-main | Analyst → Stock Researcher | 拿掉（原本用 Python 計算，改手算寫公式） | 新增 | news-event-scan | 數據標資料期間＋查詢時間；「不是投資建議」 |
| ary-vic-regulation 澳洲法規研究 | foundry-gx10-main | Analyst → Regulation Researcher | 拿掉 | 新增 | marketing-compliance-review | 引用官方來源＋法規版本／生效日期＋條號 |

為什麼改 role：`ROLE_DEPARTMENT_MAP` 把 Engineer／Analyst／Marketing 對到有 `bash` 的部門（`DEFAULT_TOOL_PERMISSIONS`）。
改成對不到的 role → General → 預設沒有 bash。已聘員工的部門不受影響。

所有舊 skill 都補上「品質檢查清單（v2）」與「做不到時」段落；台股 3 個舊 skill 的「用 Python 算」改為手算。

## 參考來源（2026-10-29 查詢）

| 角色 | 來源 | 借用 |
|---|---|---|
| 共通 | [OMC Hiring](https://1mancompany.github.io/OneManCompany/docs/guide/hiring/)、[Publish to Talent Market](https://1mancompany.github.io/OneManCompany/docs/guide/publish-to-talent-market/)、[OMC Talent Market](https://one-man-company.com/market) | 人才包結構（profile、DESCRIPTION、skills、tools） |
| 共通 | [CrewAI Crafting Effective Agents](https://docs.crewai.com/v1.11.0/en/guides/agents/crafting-effective-agents) | role／goal／backstory；80% 心力放在任務與交件格式 |
| 程式工程師 | [agency-agents Code Reviewer](https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-code-reviewer.md) | 正確性／安全／可維護／效能／測試；🔴🟡💭 分級；一次給完整意見 |
| 程式工程師 | fork `5998b66` `core/bash_guard.py` | bash 以 nobody 執行、擋 Gmail API／OAuth／secret |
| 文案 | [agency-agents Content Creator](https://github.com/msitarzewski/agency-agents/blob/HEAD/marketing/marketing-content-creator.md)、[Social Media Strategist](https://github.com/msitarzewski/agency-agents/blob/main/marketing/marketing-social-media-strategist.md) | 受眾優先、品牌語氣一致、平台化 |
| 文案／法規 | [ACCC 環保與永續宣稱](https://www.accc.gov.au/consumers/advertising-and-promotions/environmental-and-sustainability-claims)、[ACCC Advertising and selling guide](https://www.accc.gov.au/system/files/Advertising%20and%20selling%20guide%20-%20July%202021.pdf) | 「消費者無法驗證」的宣稱要有根據；避免模糊字眼；小字不能推翻大字 |
| 文案／法規 | [ACMA Avoid sending spam](https://www.acma.gov.au/avoid-sending-spam)、[Spam Act 2003](https://www.austlii.edu.au/cgi-bin/viewdoc/au/legis/cth/consol_act/sa200366/index.html) | 同意、寄件者身分、取消訂閱 |
| 市場研究員 | [agency-agents NEXUS strategy](https://github.com/msitarzewski/agency-agents/blob/main/strategy/nexus-strategy.md)（Trend Researcher）、[MetaGPT ProductManager](https://github.com/FoundationAgents/MetaGPT/blob/11cdf466/metagpt/roles/product_manager.py)（Market Research mode） | 市場研究要附來源、趨勢與機會 |
| 秘書 | [agency-agents Executive Summary Generator](https://github.com/msitarzewski/agency-agents/blob/main/support/support-executive-summary-generator.md) | SCQA、325–475 字、不加原資料沒有的假設、標出資料缺口 |
| 台股 | [TradingAgents Fundamentals Analyst](https://github.com/TauricResearch/TradingAgents/blob/61522e10/tradingagents/agents/analysts/fundamentals_analyst.py)、[TradingAgents 論文](https://arxiv.org/html/2412.20138v5) | 基本面／新聞分析師分工；報告末附整理表（**不採用**其 BUY/HOLD/SELL 交易建議） |
| 台股 | [證券交易法 §36](https://law.moj.gov.tw/LawClass/LawSingle.aspx?flno=36&pcode=G0400001)、[證交所規定](https://twse-regulation.twse.com.tw/TW/law/DOC01_print.aspx?FLCODE=FL007250&FLNO=3) | 月營收每月 10 日前公告上月份 |
| 法規 | [agency-agents Legal Compliance Checker](https://github.com/msitarzewski/agency-agents/blob/main/support/support-legal-compliance-checker.md) | 風險評估、稽核軌跡 |
| 法規 | [Food Act 1984 (Vic)](https://www.legislation.vic.gov.au/in-force/acts/food-act-1984)、[FSANZ Food Standards Code](https://www.foodstandards.gov.au/food-standards-code) | 官方法規頁有版本號與生效日期，引用時一併標注 |

ChatDev／AutoGen 沒有這 6 種角色的專門範本，未採用。
