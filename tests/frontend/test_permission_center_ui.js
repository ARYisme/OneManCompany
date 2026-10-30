/**
 * Smoke: Permission Center markup and app helpers exist.
 * Run: node --test tests/frontend/test_permission_center_ui.js
 */
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', 'frontend');

describe('permission center UI', () => {
  it('index.html has sidebar entry, modal, and save buttons', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    assert.match(html, /id="sidebar-permissions-btn"/);
    assert.match(html, /權限中心/);
    assert.match(html, /id="permissions-toolbar-btn"/);
    assert.match(html, /id="permissions-modal"/);
    assert.match(html, /id="perm-dept-matrix"/);
    assert.match(html, /id="perm-emp-select"/);
    assert.match(html, /id="perm-audit-list"/);
    assert.match(html, /儲存部門預設/);
    assert.match(html, /儲存員工例外/);
  });

  it('app.js has tri-state switches and success toasts', () => {
    const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
    assert.match(js, /openPermissionCenter\s*\(/);
    assert.match(js, /_cyclePermTri\s*\(/);
    assert.match(js, /_permTriButton\s*\(/);
    assert.match(js, /sidebar-permissions-btn/);
    assert.match(js, /部門預設已儲存/);
    assert.match(js, /員工例外已儲存/);
    assert.match(js, /\/api\/permissions/);
  });
});
