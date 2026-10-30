"""Permission center — department defaults, employee exceptions, deny-first.

Runtime resolution (deny-first)::

    if employee profile has ``tool_permissions`` key (including ``[]``):
        grants = positive entries in that list   # employee exception (replaces dept)
    else:
        grants = department default from YAML (else code DEFAULT_TOOL_PERMISSIONS)
    denies = ``!tool`` / ``-tool`` entries on the employee list
    effective = grants - denies

Changes are written to disk and take effect on the next permission check /
agent refresh — no process restart required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml
from loguru import logger

from onemancompany.core.config import (
    DEFAULT_TOOL_PERMISSIONS,
    DEFAULT_TOOL_PERMISSIONS_FALLBACK,
    DEPT_ORDER,
    HR_DIR,
    PF_DEPARTMENT,
    PF_NAME,
    PF_NICKNAME,
    PF_ROLE,
    PF_TOOL_PERMISSIONS,
    read_text_utf,
    write_text_utf,
)

PERMISSIONS_FILENAME = "tool_permissions.yaml"
PERMISSIONS_PATH = HR_DIR / PERMISSIONS_FILENAME

# Departments shown in the matrix (founding + product depts)
MATRIX_DEPARTMENTS: list[str] = list(dict.fromkeys([
    *DEPT_ORDER,
    "Executive",
    "HR",
    "Operations",
    "CEO Office",
    "Sales",
]))

# Gated tools managed in the permission center (must match common_tools _gated)
GATED_TOOL_NAMES: list[str] = [
    "bash",
    "use_tool",
    "set_project_budget",
    "set_cron",
    "stop_cron_job",
    "setup_webhook",
    "remove_webhook",
    "list_automations",
    "notify_ceo",
    "report_to_ceo",
    "start_background_task",
    "check_background_task",
    "stop_background_task",
    "list_background_tasks",
    "request_api_key",
]


def _default_departments() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dept in MATRIX_DEPARTMENTS:
        out[dept] = list(
            DEFAULT_TOOL_PERMISSIONS.get(dept, DEFAULT_TOOL_PERMISSIONS_FALLBACK)
        )
    return out


def load_department_defaults() -> dict[str, list[str]]:
    """Return department → granted gated tool names (no deny prefixes).

    Missing file → code defaults (does not create the file on read).
    """
    path = PERMISSIONS_PATH
    if not path.exists():
        return _default_departments()
    try:
        raw = yaml.safe_load(read_text_utf(path)) or {}
    except Exception as exc:
        logger.warning("Failed to read {}: {}", path, exc)
        return _default_departments()

    depts = raw.get("departments") or {}
    merged = _default_departments()
    for name, tools in depts.items():
        if isinstance(tools, list):
            merged[str(name)] = [str(t) for t in tools if t and not str(t).startswith(("!", "-"))]
        elif tools is None:
            merged[str(name)] = []
    return merged


def save_department_defaults(
    departments: dict[str, list[str]],
    *,
    actor_id: str = "ceo",
) -> dict[str, list[str]]:
    """Replace department defaults and append an audit record. Returns saved map."""
    cleaned: dict[str, list[str]] = {}
    for name, tools in departments.items():
        cleaned[str(name)] = [
            str(t) for t in (tools or [])
            if t and not str(t).startswith(("!", "-"))
        ]

    # Keep known departments; allow extra keys for custom depts
    for dept in MATRIX_DEPARTMENTS:
        cleaned.setdefault(dept, list(
            DEFAULT_TOOL_PERMISSIONS.get(dept, DEFAULT_TOOL_PERMISSIONS_FALLBACK)
        ))

    prev = load_department_defaults()
    PERMISSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": actor_id,
        "departments": cleaned,
    }
    write_text_utf(
        PERMISSIONS_PATH,
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
    )
    _audit_permission_change(
        actor_id=actor_id,
        target="departments",
        action="update_department_defaults",
        before=prev,
        after=cleaned,
    )
    refresh_all_employee_agent_tools()
    return cleaned


def split_permission_tokens(tokens: list[str] | None) -> tuple[set[str], set[str]]:
    """Split raw tokens into (grants, denies)."""
    grants: set[str] = set()
    denies: set[str] = set()
    for raw in tokens or []:
        t = str(raw).strip()
        if not t:
            continue
        if t.startswith("!") or t.startswith("-"):
            denies.add(t[1:])
        else:
            grants.add(t)
    return grants, denies


def has_employee_exception(emp_data: dict) -> bool:
    """True when profile explicitly sets tool_permissions (including empty list)."""
    return PF_TOOL_PERMISSIONS in emp_data


def effective_gated_grants(emp_data: dict) -> set[str]:
    """Resolve effective gated tool names for an employee (deny-first)."""
    dept = str(emp_data.get(PF_DEPARTMENT) or "General")
    dept_defaults = set(load_department_defaults().get(dept, DEFAULT_TOOL_PERMISSIONS_FALLBACK))

    if has_employee_exception(emp_data):
        grants, denies = split_permission_tokens(emp_data.get(PF_TOOL_PERMISSIONS) or [])
        # Employee exception replaces department defaults for grants
        return grants - denies

    return dept_defaults


def is_gated_tool_allowed(emp_data: dict, tool_name: str) -> bool:
    grants, denies = split_permission_tokens(
        emp_data.get(PF_TOOL_PERMISSIONS) if has_employee_exception(emp_data) else None
    )
    if tool_name in denies:
        return False
    if has_employee_exception(emp_data):
        return tool_name in grants
    dept = str(emp_data.get(PF_DEPARTMENT) or "General")
    return tool_name in set(
        load_department_defaults().get(dept, DEFAULT_TOOL_PERMISSIONS_FALLBACK)
    )


async def set_employee_permissions(
    employee_id: str,
    tokens: list[str],
    *,
    actor_id: str = "ceo",
) -> list[str]:
    """Persist employee tool_permissions exception and audit. Returns saved tokens."""
    from onemancompany.core import store as store_mod
    from onemancompany.core.config import DirtyCategory

    emp = store_mod.load_employee(employee_id)
    if not emp:
        raise ValueError(f"Employee {employee_id} not found")

    before = list(emp.get(PF_TOOL_PERMISSIONS) or []) if has_employee_exception(emp) else None
    cleaned = [str(t).strip() for t in tokens if str(t).strip()]

    await store_mod.save_employee(employee_id, {PF_TOOL_PERMISSIONS: cleaned})
    store_mod._read_cache_invalidate(DirtyCategory.EMPLOYEES)

    _audit_permission_change(
        actor_id=actor_id,
        target=employee_id,
        action="update_employee_permissions",
        before=before,
        after=cleaned,
    )
    refresh_employee_agent_tools(employee_id)
    return cleaned


async def clear_employee_exception(
    employee_id: str,
    *,
    actor_id: str = "ceo",
) -> None:
    """Remove employee exception so department defaults apply again."""
    from onemancompany.core import store as store_mod
    from onemancompany.core.config import DirtyCategory, PROFILE_FILENAME

    emp = store_mod.load_employee(employee_id)
    if not emp:
        raise ValueError(f"Employee {employee_id} not found")

    before = list(emp.get(PF_TOOL_PERMISSIONS) or []) if has_employee_exception(emp) else None

    profile_path = store_mod.EMPLOYEES_DIR / employee_id / PROFILE_FILENAME
    data = store_mod._read_yaml(profile_path)  # disk truth, no injected fields
    if PF_TOOL_PERMISSIONS in data:
        data.pop(PF_TOOL_PERMISSIONS, None)
        store_mod._write_yaml(profile_path, data)
        store_mod.mark_dirty(DirtyCategory.EMPLOYEES)
        store_mod._read_cache_invalidate(DirtyCategory.EMPLOYEES)

    _audit_permission_change(
        actor_id=actor_id,
        target=employee_id,
        action="clear_employee_exception",
        before=before,
        after=None,
    )
    refresh_employee_agent_tools(employee_id)


def refresh_employee_agent_tools(employee_id: str) -> None:
    """Hot-reload proxied tools on the live agent handle if present."""
    try:
        from onemancompany.core.tool_registry import tool_registry
        from onemancompany.core.vessel import employee_manager

        handle = employee_manager.get_handle(employee_id) if employee_manager else None
        agent = getattr(handle, "agent", None) if handle else None
        if agent is None:
            # Some handles expose the runner differently
            agent = handle
        if agent is None:
            return
        if hasattr(agent, "_agent_tools"):
            tools = tool_registry.get_proxied_tools_for(employee_id)
            agent._agent_tools = tools
            if hasattr(agent, "_refresh_agent"):
                agent._refresh_agent()
            elif hasattr(agent, "_agent"):
                from langgraph.prebuilt import create_react_agent
                from onemancompany.agents.base import make_llm
                agent._agent = create_react_agent(
                    model=make_llm(employee_id),
                    tools=tools,
                )
    except Exception as exc:
        logger.debug("refresh_employee_agent_tools({}) failed: {}", employee_id, exc)


def refresh_all_employee_agent_tools() -> None:
    try:
        from onemancompany.core.store import load_all_employees
        for eid in load_all_employees():
            refresh_employee_agent_tools(eid)
    except Exception as exc:
        logger.debug("refresh_all_employee_agent_tools failed: {}", exc)


def _audit_permission_change(
    *,
    actor_id: str,
    target: str,
    action: str,
    before: Any,
    after: Any,
) -> None:
    try:
        from onemancompany.core.journal import EvidenceKind, EvidenceRecord, Journal

        Journal().write_sync(
            EvidenceRecord(
                kind=EvidenceKind.PERMISSION_CHANGED,
                agent=actor_id or "system",
                employee_id=target if target != "departments" else None,
                payload={
                    "action": action,
                    "target": target,
                    "actor_id": actor_id,
                    "before": before,
                    "after": after,
                },
            )
        )
    except Exception as exc:
        logger.debug("permission journal audit failed: {}", exc)

    try:
        from onemancompany.core.store import append_activity_sync

        append_activity_sync(
            {
                "type": "permission_changed",
                "actor_id": actor_id,
                "target": target,
                "action": action,
                "before": before,
                "after": after,
            }
        )
    except Exception as exc:
        logger.debug("permission activity audit failed: {}", exc)


def build_permissions_snapshot() -> dict:
    """Payload for GET /api/permissions — matrix + employee exceptions + recent audit."""
    from onemancompany.core.store import load_all_employees, load_activity_log

    departments = load_department_defaults()
    employees_out = []
    for eid, emp in sorted(load_all_employees().items()):
        exception = has_employee_exception(emp)
        tokens = list(emp.get(PF_TOOL_PERMISSIONS) or []) if exception else []
        employees_out.append({
            "id": eid,
            "name": emp.get(PF_NAME) or eid,
            "nickname": emp.get(PF_NICKNAME) or "",
            "role": emp.get(PF_ROLE) or "",
            "department": emp.get(PF_DEPARTMENT) or "General",
            "has_exception": exception,
            "tool_permissions": tokens,
            "effective": sorted(effective_gated_grants(emp)),
        })

    audit = [
        e for e in load_activity_log()
        if isinstance(e, dict) and e.get("type") in ("permission_changed", "permission_denied")
    ][:50]

    return {
        "gated_tools": list(GATED_TOOL_NAMES),
        "departments": departments,
        "department_order": MATRIX_DEPARTMENTS,
        "employees": employees_out,
        "audit": audit,
    }
