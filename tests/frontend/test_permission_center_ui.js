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
  it('index.html has permissions modal and toolbar button', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    assert.match(html, /id="permissions-toolbar-btn"/);
    assert.match(html, /id="permissions-modal"/);
    assert.match(html, /id="perm-dept-matrix"/);
    assert.match(html, /id="perm-emp-select"/);
    assert.match(html, /id="perm-audit-list"/);
  });

  it('app.js exposes openPermissionCenter and save helpers', () => {
    const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
    assert.match(js, /openPermissionCenter\s*\(/);
    assert.match(js, /_savePermissionDepartments\s*\(/);
    assert.match(js, /_savePermissionEmployee\s*\(/);
    assert.match(js, /_clearPermissionEmployee\s*\(/);
    assert.match(js, /\/api\/permissions/);
  });
});
