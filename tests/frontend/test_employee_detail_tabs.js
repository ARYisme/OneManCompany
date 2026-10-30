/**
 * Smoke: employee detail four-tab layout.
 * Run: node --test tests/frontend/test_employee_detail_tabs.js
 */
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..', 'frontend');

describe('employee detail tabs', () => {
  it('index.html has four tabs and read-only tool permission section', () => {
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    for (const tab of ['overview', 'tasks', 'records', 'coaching']) {
      assert.match(html, new RegExp(`data-emp-tab="${tab}"`));
      assert.match(html, new RegExp(`data-emp-panel="${tab}"`));
    }
    assert.match(html, /id="emp-detail-tool-perms"/);
    assert.match(html, /id="emp-open-perm-center-btn"/);
    assert.match(html, /工具權限（唯讀）/);
    // 1-on-1 stays under coaching tab
    assert.match(html, /data-emp-panel="coaching"[\s\S]*id="emp-oneonone-btn"/);
  });

  it('app.js switches tabs and loads read-only tool perms', () => {
    const js = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
    assert.match(js, /_switchEmployeeTab\s*\(/);
    assert.match(js, /_loadEmployeeToolPermTags\s*\(/);
    assert.match(js, /effective_tool_permissions/);
    assert.match(js, /openPermissionCenter\(/);
  });
});
