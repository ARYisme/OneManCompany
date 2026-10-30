"""Unit tests for human-readable capability catalog (display/UX layer)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml


class TestCapabilityCatalog:
    def test_catalog_covers_named_tools_and_other(self):
        from onemancompany.core.capability_catalog import (
            all_capabilities,
            other_gated_tools,
        )
        from onemancompany.core.permissions import GATED_TOOL_NAMES

        caps = all_capabilities()
        ids = [c.id for c in caps]
        assert "bash" in ids
        assert "web_search" in ids
        assert "other" in ids
        covered = set()
        for c in caps:
            covered.update(c.gated_tools)
        # every gated tool appears in some capability (named or other)
        assert set(GATED_TOOL_NAMES) <= covered | set(other_gated_tools())
        assert set(GATED_TOOL_NAMES) == covered

    def test_bash_is_red(self):
        from onemancompany.core.capability_catalog import CAPABILITY_CATALOG

        bash = next(c for c in CAPABILITY_CATALOG if c.id == "bash")
        assert bash.risk == "red"
        assert "信任" in bash.description or "系統" in bash.description

    def test_presets_have_three_roles(self):
        from onemancompany.core.capability_catalog import (
            CAPABILITY_PRESETS,
            presets_public_list,
        )

        assert set(CAPABILITY_PRESETS) >= {"general", "researcher", "engineer"}
        pub = presets_public_list()
        assert {p["id"] for p in pub} >= {"general", "researcher", "engineer"}
        assert CAPABILITY_PRESETS["engineer"]["states"]["bash"] == "on"
        assert CAPABILITY_PRESETS["general"]["states"]["bash"] == "off"

    def test_apply_tokens_preserves_unmanaged_and_clear_on_all_inherit(self):
        from onemancompany.core.capability_catalog import (
            apply_capability_states_to_tokens,
        )

        # Turning bash off, use_tool on; leave cron inherit → only those tokens
        tokens = apply_capability_states_to_tokens(
            capability_states={"bash": "off", "use_tool": "on", "cron": "inherit"},
            existing_tokens=["bash", "notify_ceo"],
            had_exception=True,
        )
        assert tokens is not None
        assert "use_tool" in tokens
        assert "!bash" in tokens
        # notify_ceo was unmanaged by this save set — preserved if not in managed set
        # notify is under notify capability; we didn't send notify → preserved
        assert "notify_ceo" in tokens

        cleared = apply_capability_states_to_tokens(
            capability_states={
                "bash": "inherit",
                "use_tool": "inherit",
                "cron": "inherit",
                "notify": "inherit",
                "other": "inherit",
            },
            existing_tokens=["bash"],
            had_exception=True,
        )
        assert cleared is None

    def test_resolve_employee_capability_states_no_mutation(self, tmp_path, monkeypatch):
        from onemancompany.core import capability_catalog as cat
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({"departments": {"Engineering": ["bash", "use_tool"]}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        emp = {
            "department": "Engineering",
            "tool_permissions": ["use_tool", "!bash"],
            "permissions": ["web_search", "company_file_access"],
        }
        before = yaml.safe_dump(emp)
        states = cat.resolve_employee_capability_states(emp, "00099")
        assert states["bash"]["state"] == "off"
        assert states["use_tool"]["state"] == "on"
        assert states["web_search"]["state"] == "on"
        assert states["email_draft"]["display_only"] is True
        assert yaml.safe_dump(emp) == before  # no mutation

    def test_capability_labels_plain_names(self, tmp_path, monkeypatch):
        from onemancompany.core import capability_catalog as cat
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({"departments": {"General": ["use_tool"]}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        emp = {
            "department": "General",
            "permissions": ["web_search"],
        }
        tags = cat.capability_labels_for_effective(emp, "00001")
        names = [t["name"] for t in tags]
        assert "上網查資料" in names
        assert "使用公司工具和設備" in names
        assert "bash" not in names

    def test_dept_effective_on_for_gated_inherit(self, tmp_path, monkeypatch):
        from onemancompany.core import capability_catalog as cat
        from onemancompany.core import permissions as perm

        path = tmp_path / "tool_permissions.yaml"
        path.write_text(
            yaml.safe_dump({"version": 2, "departments": {"Engineering": []}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(perm, "PERMISSIONS_PATH", path)

        emp = {"department": "Engineering"}  # no exception → inherit
        states = cat.resolve_employee_capability_states(emp, "00099")
        assert states["bash"]["state"] == "inherit"
        # Engineering code default includes bash
        assert states["bash"]["dept_effective_on"] is True
        assert states["use_tool"]["dept_effective_on"] is True
