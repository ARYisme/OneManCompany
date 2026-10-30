/**
 * Smoke: Permission Center capability UX markup and helpers.
 * Run: node --test tests/frontend/test_permission_center_ui.js
 */
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', 'frontend');

describe('permission center UI', () => {
  it('index.html has capability switches, presets, and collapsed advanced', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    assert.match(html, /id="sidebar-permissions-btn"/);
    assert.match(html, /權限中心/);
    assert.match(html, /id="permissions-modal"/);
    assert.match(html, /id="perm-capability-list"/);
    assert.match(html, /id="perm-presets"/);
    assert.match(html, /儲存能力設定/);
    assert.match(html, /id="perm-advanced"/);
    assert.match(html, /進階設定/);
    assert.match(html, /id="perm-dept-matrix"/);
    assert.match(html, /id="perm-emp-select"/);
    assert.match(html, /id="perm-audit-list"/);
    assert.match(html, /儲存部門預設/);
  });

  it('app.js has capability cycle, red confirm, presets, and API save', () => {
    const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
    assert.match(js, /openPermissionCenter\s*\(/);
    assert.match(js, /_cycleCapabilitySwitch\s*\(/);
    assert.match(js, /_applyCapabilityPreset\s*\(/);
    assert.match(js, /_savePermissionCapabilities\s*\(/);
    assert.match(js, /危險能力/);
    assert.match(js, /capability_states/);
    assert.match(js, /capability_labels/);
    assert.match(js, /\/api\/permissions/);
  });

  it('css has risk colors and capability row styles', () => {
    const css = fs.readFileSync(path.join(root, 'omc-readable.css'), 'utf8');
    assert.match(css, /\.cap-row/);
    assert.match(css, /\.risk-red/);
    assert.match(css, /\.cap-switch/);
    assert.match(css, /\.perm-advanced/);
  });
});
