# ARY fork 變更紀錄（ARYisme/OneManCompany，branch `ary-readable-ui`）

此 fork 以上游 1mancompany/OneManCompany `3fde188` 為基底（Apache-2.0）。以下為 ARY 的修改，時間為 AEDT。

## 2026-10-28

- `web_fetch` 工具：市場研究員（`ary-market-researcher`）可打開公開網頁讀全文。
  後端 crawl4ai（有 token 時）＋標準庫 fallback；SSRF 防護、20 秒 timeout、2 MB 上限。
  詳見 [web-tools.md](web-tools.md)。
- `38f8e27` talents：補上 6 位 ary-* 員工的 SOP skills。
- `63509d1` talents：新增 6 位本地繁中員工包（ary-coder、ary-market-researcher、ary-copywriter、
  ary-vic-regulation、ary-tw-stock、ary-secretary）。
- `6d10595` ui：員工中文名稱與對話以 opencc-js 轉為台灣繁體（只影響顯示）。
- `7ea1643` ui：全站字體統一為 Noto Sans TC，移除像素字體（CSS、canvas、G6、xterm），`lang=zh-Hant`。
- `7fa82ae` ui：系統／繁中可讀字體與手機單欄版面。
