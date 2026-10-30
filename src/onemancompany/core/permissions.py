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


def _code_default_grants(dept: str) -> set[str]:
    return set(DEFAULT_TOOL_PERMISSIONS.get(dept, DEFAULT_TOOL_PERMISSIONS_FALLBACK))


def _default_departments() -> dict[str, list[str]]:
    """Resolved allow-lists (code defaults) — used when no YAML overrides exist."""
    return {dept: sorted(_code_default_grants(dept)) for dept in MATRIX_DEPARTMENTS}


def _load_permissions_yaml() -> dict:
    path = PERMISSIONS_PATH
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(read_text_utf(path)) or {}
    except Exception as exc:
        logger.warning("Failed to read {}: {}", path, exc)
        return {}


def permissions_file_version() -> int:
    raw = _load_permissions_yaml()
    try:
        return int(raw.get("version") or 1)
    except (TypeError, ValueError):
        return 1


def load_department_raw_tokens() -> dict[str, list[str]]:
    """Raw department tokens from YAML (may include ``!tool``). Missing file → {}."""
    raw = _load_permissions_yaml()
    depts = raw.get("departments") or {}
    out: dict[str, list[str]] = {}
    for name, tools in depts.items():
        if isinstance(tools, list):
            out[str(name)] = [str(t).strip() for t in tools if str(t).strip()]
        elif tools is None:
            out[str(name)] = []
    return out


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


def token_state(tokens: list[str] | None, tool_name: str, *, empty_is_deny: bool = False) -> str:
    """Return ``allow`` | ``deny`` | ``inherit`` for one tool against a token list.

    ``tokens is None`` → inherit (no override row).
    ``tokens == []`` with empty_is_deny → deny (legacy employee empty exception).
    ``tokens == []`` without empty_is_deny → inherit (dept row means all inherit).
    """
    if tokens is None:
        return "inherit"
    if tokens == []:
        return "deny" if empty_is_deny else "inherit"
    grants, denies = split_permission_tokens(tokens)
    if tool_name in denies:
        return "deny"
    if tool_name in grants:
        return "allow"
    return "inherit"


def department_tool_state(dept: str, tool_name: str) -> str:
    """v2+: omit = inherit. v1 legacy files: omit = deny (old checkbox matrix)."""
    raw_map = load_department_raw_tokens()
    if not PERMISSIONS_PATH.exists():
        return "inherit"
    if dept not in raw_map:
        return "inherit"
    state = token_state(raw_map[dept], tool_name, empty_is_deny=False)
    if state != "inherit":
        return state
    # Legacy v1: unlisted tool meant "not granted"
    if permissions_file_version() < 2:
        return "deny"
    return "inherit"


def department_allows(dept: str, tool_name: str) -> bool:
    state = department_tool_state(dept, tool_name)
    if state == "deny":
        return False
    if state == "allow":
        return True
    return tool_name in _code_default_grants(dept)


def load_department_defaults() -> dict[str, list[str]]:
    """Return department → *effective* granted gated tool names (resolved)."""
    out: dict[str, list[str]] = {}
    for dept in MATRIX_DEPARTMENTS:
        out[dept] = sorted(t for t in GATED_TOOL_NAMES if department_allows(dept, t))
    # Include any extra depts from YAML
    for dept in load_department_raw_tokens():
        if dept not in out:
            out[dept] = sorted(t for t in GATED_TOOL_NAMES if department_allows(dept, t))
    return out


def save_department_defaults(
    departments: dict[str, list[str]],
    *,
    actor_id: str = "ceo",
) -> dict[str, list[str]]:
    """Save raw department tokens (``tool`` / ``!tool``; omit = inherit). Returns raw map."""
    cleaned: dict[str, list[str]] = {}
    for name, tools in departments.items():
        toks: list[str] = []
        seen: set[str] = set()
        for t in tools or []:
            s = str(t).strip()
            if not s:
                continue
            key = s[1:] if s.startswith(("!", "-")) else s
            if key in seen:
                continue
            seen.add(key)
            toks.append(s)
        cleaned[str(name)] = toks

    for dept in MATRIX_DEPARTMENTS:
        cleaned.setdefault(dept, [])

    prev = load_department_raw_tokens()
    PERMISSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,  # omit = inherit; ``!tool`` = deny; ``tool`` = allow
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


def has_employee_exception(emp_data: dict) -> bool:
    """True when profile explicitly sets tool_permissions (including empty list)."""
    return PF_TOOL_PERMISSIONS in emp_data


def employee_tool_state(emp_data: dict, tool_name: str) -> str:
    if not has_employee_exception(emp_data):
        return "inherit"
    tokens = emp_data.get(PF_TOOL_PERMISSIONS)
    if tokens is None:
        return "inherit"
    return token_state(list(tokens), tool_name, empty_is_deny=True)


def is_gated_tool_allowed(emp_data: dict, tool_name: str) -> bool:
    dept = str(emp_data.get(PF_DEPARTMENT) or "General")
    dept_ok = department_allows(dept, tool_name)

    state = employee_tool_state(emp_data, tool_name)
    if state == "deny":
        return False
    if state == "allow":
        return True
    return dept_ok


def effective_gated_grants(emp_data: dict) -> set[str]:
    """Resolve effective gated tool names for an employee (deny-first)."""
    return {t for t in GATED_TOOL_NAMES if is_gated_tool_allowed(emp_data, t)}


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
    """Payload for GET /api/permissions — capabilities + matrix + audit."""
    from onemancompany.core.capability_catalog import (
        all_capabilities,
        capability_public_dict,
        presets_public_list,
        resolve_employee_capability_states,
    )
    from onemancompany.core.store import load_all_employees, load_activity_log

    raw = load_department_raw_tokens()
    dept_states: dict[str, dict[str, str]] = {}
    for dept in MATRIX_DEPARTMENTS:
        dept_states[dept] = {
            t: department_tool_state(dept, t) for t in GATED_TOOL_NAMES
        }
    for dept in raw:
        if dept not in dept_states:
            dept_states[dept] = {
                t: department_tool_state(dept, t) for t in GATED_TOOL_NAMES
            }

    employees_out = []
    for eid, emp in sorted(load_all_employees().items()):
        exception = has_employee_exception(emp)
        tokens = list(emp.get(PF_TOOL_PERMISSIONS) or []) if exception else []
        tool_states = {t: employee_tool_state(emp, t) for t in GATED_TOOL_NAMES}
        cap_states = resolve_employee_capability_states(emp, eid)
        employees_out.append({
            "id": eid,
            "name": emp.get(PF_NAME) or eid,
            "nickname": emp.get(PF_NICKNAME) or "",
            "role": emp.get(PF_ROLE) or "",
            "department": emp.get(PF_DEPARTMENT) or "General",
            "has_exception": exception,
            "tool_permissions": tokens,
            "tool_states": tool_states,
            "capability_states": cap_states,
            "effective": sorted(effective_gated_grants(emp)),
        })

    audit = [
        e for e in load_activity_log()
        if isinstance(e, dict) and e.get("type") in ("permission_changed", "permission_denied")
    ][:50]

    return {
        "capabilities": [capability_public_dict(c) for c in all_capabilities()],
        "presets": presets_public_list(),
        "gated_tools": list(GATED_TOOL_NAMES),
        "departments": load_department_defaults(),
        "department_tokens": raw,
        "department_states": dept_states,
        "department_order": MATRIX_DEPARTMENTS,
        "employees": employees_out,
        "audit": audit,
    }


async def apply_employee_capabilities(
    employee_id: str,
    capability_states: dict[str, str],
    *,
    actor_id: str = "ceo",
) -> dict:
    """Apply human capability toggles → existing permission stores. Hot-applies.

    Does not rewrite capabilities the caller omitted. Display-only caps are ignored.
    """
    from onemancompany.core.capability_catalog import (
        apply_capability_states_to_profile_keys,
        apply_capability_states_to_tokens,
        all_capabilities,
    )
    from onemancompany.core import store as store_mod
    from onemancompany.core.config import DirtyCategory, PF_PERMISSIONS

    emp = store_mod.load_employee(employee_id)
    if not emp:
        raise ValueError(f"Employee {employee_id} not found")

    # Drop display-only / unknown
    caps = {c.id: c for c in all_capabilities()}
    cleaned: dict[str, str] = {}
    for cid, st in (capability_states or {}).items():
        cap = caps.get(cid)
        if not cap or cap.display_only:
            continue
        if st not in ("on", "off", "inherit"):
            continue
        cleaned[cid] = st

    had_exception = has_employee_exception(emp)
    existing_tokens = (
        list(emp.get(PF_TOOL_PERMISSIONS) or []) if had_exception else None
    )
    new_tokens = apply_capability_states_to_tokens(
        capability_states=cleaned,
        existing_tokens=existing_tokens,
        had_exception=had_exception,
    )

    before_tools = existing_tokens
    if new_tokens is None:
        after_tools = None
        if had_exception:
            await clear_employee_exception(employee_id, actor_id=actor_id)
    elif sorted(new_tokens) != sorted(existing_tokens or []):
        after_tools = await set_employee_permissions(
            employee_id, new_tokens, actor_id=actor_id
        )
    else:
        after_tools = list(existing_tokens or [])

    # Soft profile.permissions
    new_profile = apply_capability_states_to_profile_keys(
        capability_states=cleaned,
        existing_profile_perms=list(emp.get(PF_PERMISSIONS) or []),
    )
    if sorted(new_profile) != sorted(emp.get(PF_PERMISSIONS) or []):
        await store_mod.save_employee(employee_id, {PF_PERMISSIONS: new_profile})
        store_mod._read_cache_invalidate(DirtyCategory.EMPLOYEES)
        _audit_permission_change(
            actor_id=actor_id,
            target=employee_id,
            action="update_profile_permissions",
            before=list(emp.get(PF_PERMISSIONS) or []),
            after=new_profile,
        )

    # web_fetch whitelist
    if "web_fetch" in cleaned:
        from onemancompany.agents.onboarding import (
            register_tool_user,
            unregister_tool_user,
        )
        st = cleaned["web_fetch"]
        if st == "on":
            register_tool_user("web_fetch", employee_id)
        elif st == "off":
            unregister_tool_user("web_fetch", employee_id)
        # inherit: leave whitelist alone

    refresh_employee_agent_tools(employee_id)
    return {
        "employee_id": employee_id,
        "tool_permissions": after_tools,
        "permissions": new_profile,
        "capability_states_applied": cleaned,
        "before_tool_permissions": before_tools,
    }
