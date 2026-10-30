/**
 * Smoke: Permission Center capability UX + inherit effective labels.
 * Run: node --test tests/frontend/test_permission_center_ui.js
 */
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', 'frontend');

describe('permission center UI', () => {
  it('toolbar lock is icon-only; sidebar keeps label', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    assert.match(html, /id="permissions-toolbar-btn"[^>]*title="權限中心"/);
    assert.doesNotMatch(
      html,
      /id="permissions-toolbar-btn"[^>]*>[\s\S]*toolbar-perm-label/,
    );
    assert.match(html, /id="sidebar-permissions-btn"[\s\S]*權限中心/);
    assert.match(html, /id="perm-show-builtins-btn"/);
    assert.match(html, /顯示內建預設/);
    assert.match(html, /id="perm-capability-list"/);
    assert.match(html, /id="perm-advanced"/);
  });

  it('app.js shows inherit effective labels and three-column employee grid', () => {
    const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
    assert.match(js, /繼承（允許）/);
    assert.match(js, /繼承（不給）/);
    assert.match(js, /跟部門一樣（目前：開）/);
    assert.match(js, /跟部門一樣（目前：關）/);
    assert.match(js, /_togglePermissionBuiltins/);
    assert.match(js, /perm-emp-grid-3/);
    assert.match(js, /部門給的/);
    assert.match(js, /最終結果/);
    assert.match(js, /code_defaults/);
    assert.match(js, /capability_states/);
  });

  it('css has inherit-allow/deny and compact sidebar', () => {
    const css = fs.readFileSync(path.join(root, 'omc-readable.css'), 'utf8');
    assert.match(css, /\.state-inherit-allow/);
    assert.match(css, /\.state-inherit-deny/);
    assert.match(css, /\.perm-tri\.explicit/);
    assert.match(css, /\.sidebar-perm-btn[\s\S]*font-size:\s*11px/);
  });
});
