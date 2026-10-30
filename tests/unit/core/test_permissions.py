"""Unit tests for core/permissions.py — department defaults + employee exceptions."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml


class TestEffectiveGatedGrants:
    def test_no_exception_uses_department_default(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({
                "departments": {
                    "Engineering": ["bash", "use_tool"],
                    "General": [],
                }
            }),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        grants = perm.effective_gated_grants({
            "department": "Engineering",
            # no tool_permissions key
        })
        assert grants == {"bash", "use_tool"}

    def test_empty_exception_blocks_department_default(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({"departments": {"Analytics": ["bash", "use_tool"]}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        # 00006 style: explicit empty list
        grants = perm.effective_gated_grants({
            "department": "Analytics",
            "tool_permissions": [],
        })
        assert grants == set()
        assert perm.is_gated_tool_allowed(
            {"department": "Analytics", "tool_permissions": []}, "bash"
        ) is False

    def test_deny_prefix_wins(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm

        monkeypatch.setattr(perm, "PERMISSIONS_PATH", tmp_path / "missing.yaml")
        assert perm.is_gated_tool_allowed(
            {"department": "General", "tool_permissions": ["bash", "!bash"]},
            "bash",
        ) is False

    def test_save_department_defaults_writes_and_audits(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        audits: list[dict] = []
        monkeypatch.setattr(
            perm, "_audit_permission_change",
            lambda **kw: audits.append(kw),
        )
        monkeypatch.setattr(perm, "refresh_all_employee_agent_tools", lambda: None)

        saved = perm.save_department_defaults(
            {"Engineering": ["bash", "!use_tool"], "General": []},
            actor_id="ceo",
        )
        assert path.exists()
        assert "bash" in saved["Engineering"]
        assert "!use_tool" in saved["Engineering"]
        assert perm.department_tool_state("Engineering", "bash") == "allow"
        assert perm.department_tool_state("Engineering", "use_tool") == "deny"
        assert audits and audits[0]["action"] == "update_department_defaults"
        assert audits[0]["actor_id"] == "ceo"

    def test_employee_inherit_falls_through_to_department(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({"departments": {"Engineering": ["bash"]}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        emp = {
            "department": "Engineering",
            "tool_permissions": ["!use_tool"],  # deny use_tool; bash inherits
        }
        assert perm.employee_tool_state(emp, "bash") == "inherit"
        assert perm.employee_tool_state(emp, "use_tool") == "deny"
        assert perm.is_gated_tool_allowed(emp, "bash") is True
        assert perm.is_gated_tool_allowed(emp, "use_tool") is False


class TestSetEmployeePermissions:
    @pytest.mark.asyncio
    async def test_set_and_clear_exception(self, tmp_path, monkeypatch):
        from onemancompany.core import permissions as perm
        from onemancompany.core import store as store_mod
        from onemancompany.core.config import DirtyCategory

        emp_dir = tmp_path / "employees" / "00099"
        emp_dir.mkdir(parents=True)
        profile = emp_dir / "profile.yaml"
        profile.write_text(
            yaml.safe_dump({
                "name": "Test",
                "role": "Engineer",
                "department": "Engineering",
            }),
            encoding="utf-8",
        )

        monkeypatch.setattr(store_mod, "EMPLOYEES_DIR", tmp_path / "employees")
        monkeypatch.setattr(perm, "refresh_employee_agent_tools", lambda *_a, **_k: None)
        audits: list[dict] = []
        monkeypatch.setattr(
            perm, "_audit_permission_change",
            lambda **kw: audits.append(kw),
        )

        # Bypass conftest bridge that may hide disk: call store with redirected dir
        saved = await perm.set_employee_permissions(
            "00099", ["bash", "!use_tool"], actor_id="ceo"
        )
        assert saved == ["bash", "!use_tool"]
        data = yaml.safe_load(profile.read_text(encoding="utf-8"))
        assert data["tool_permissions"] == ["bash", "!use_tool"]

        await perm.clear_employee_exception("00099", actor_id="ceo")
        data = yaml.safe_load(profile.read_text(encoding="utf-8"))
        assert "tool_permissions" not in data
        assert any(a["action"] == "clear_employee_exception" for a in audits)
