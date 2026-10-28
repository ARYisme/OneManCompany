/**
 * zh-tw-display.js — ARY fork: DISPLAY-LAYER ONLY Traditional Chinese (Taiwan).
 *
 * Converts Simplified Chinese → Traditional Chinese (Taiwan phrases, opencc-js
 * cn → twp) for text that is *rendered* in:
 *   1. employee Chinese names (nicknames) — roster, office canvas name tags,
 *      tooltips, chat headers, modals, 1-on-1 / meeting lists;
 *   2. what employees say to the CEO — chat bubbles, CEO console, 1-on-1,
 *      meetings, interviews, reports/popups, activity & execution logs.
 *
 * It never touches: inputs/textarea/select/option values, contenteditable,
 * code/pre blocks, inline `code` / ``` fenced spans, attributes (data-*, value),
 * or anything sent back to the server. English text is unaffected (only CJK
 * characters can change). UI labels are left as they are.
 *
 * Kill switch: localStorage.setItem('omc_zh_tw', 'off') then reload.
 */
(function () {
  'use strict';

  const CJK = /[\u3400-\u9fff\uf900-\ufaff]/;
  const CODE_SPLIT = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)/;

  let disabled = false;
  try { disabled = (localStorage.getItem('omc_zh_tw') || '').toLowerCase() === 'off'; } catch (e) { /* ignore */ }

  let textConv = null; // cn → twp (phrases), for dialogue
  let nameConv = null; // cn → tw (characters only), for names
  if (!disabled && window.OpenCC && typeof window.OpenCC.Converter === 'function') {
    try {
      textConv = window.OpenCC.Converter({ from: 'cn', to: 'twp' });
      nameConv = window.OpenCC.Converter({ from: 'cn', to: 'tw' });
    } catch (e) {
      console.warn('[zh-TW] OpenCC init failed', e);
    }
  }

  function conv(text) {
    if (!textConv || typeof text !== 'string' || !CJK.test(text)) return text;
    try {
      const parts = text.split(CODE_SPLIT);
      for (let i = 0; i < parts.length; i += 2) {
        if (CJK.test(parts[i])) parts[i] = textConv(parts[i]);
      }
      return parts.join('');
    } catch (e) {
      return text;
    }
  }

  function name(text) {
    if (!nameConv || typeof text !== 'string' || !CJK.test(text)) return text;
    try { return nameConv(text); } catch (e) { return text; }
  }

  // Containers whose rendered text is employee names or employee dialogue.
  const SCOPE = [
    '#roster-list', '#tooltip',
    '#ceo-conv-messages', '#ceo-oneonone-items', '#right-panel-chat',
    '#oneonone-chat', '#oneonone-chat-title',
    '#meeting-chat-messages', '#meeting-participants',
    '#interview-chat',
    '#emp-modal-title', '#emp-detail-name', '#emp-detail-nickname',
    '#emp-detail-logs', '#emp-detail-progress',
    '#ex-employee-list', '#onboarding-progress-list',
    '#project-detail-content', '#generic-popup-body', '#announcements-list',
    '.chat-panel-messages', '.mention-name', '.ceo-msg', '.chat-bubble',
  ].join(',');

  // Never convert inside these (inputs, code, editable fields, terminals).
  const SKIP = [
    'input', 'textarea', 'select', 'option', 'script', 'style', 'code', 'pre',
    '[contenteditable]', '[contenteditable=""]', '[contenteditable="true"]',
    '.project-name-editable', '.inline-edit-input', '[data-zh-skip]', '.xterm',
    '.ceo-tool-args', '.ceo-tool-result', '.ceo-msg--ceo',
  ].join(',');

  function convertTextNode(node) {
    const parent = node.parentElement;
    if (!parent || !CJK.test(node.data)) return;
    if (!parent.closest(SCOPE) || parent.closest(SKIP)) return;
    const out = conv(node.data);
    if (out !== node.data) node.data = out;
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) { convertTextNode(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    if (root.closest(SKIP)) return;
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (CJK.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    const nodes = [];
    while (tw.nextNode()) nodes.push(tw.currentNode);
    nodes.forEach(convertTextNode);
  }

  function start() {
    if (!textConv || !document.body) return;
    walk(document.body);
    const mo = new MutationObserver((records) => {
      for (const r of records) {
        if (r.type === 'characterData') convertTextNode(r.target);
        else r.addedNodes.forEach(walk);
      }
    });
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  window.OmcZhTW = { conv, name, enabled: !!textConv };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
