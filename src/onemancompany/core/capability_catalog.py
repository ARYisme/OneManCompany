"""Human-friendly capability catalog for the Permission Center.

Maps plain-language「能力」to underlying tool / profile permission names.
Does not change enforcement by itself — callers translate capability toggles
into existing tool_permissions / profile permissions tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from onemancompany.core.permissions import GATED_TOOL_NAMES


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    description: str
    risk: str  # green | yellow | red
    risk_label: str
    # Gated LangChain tool names controlled via tool_permissions
    gated_tools: tuple[str, ...] = ()
    # Soft profile.permissions keys (company_file_access, web_search, …)
    profile_keys: tuple[str, ...] = ()
    # Special asset tool id (e.g. web_fetch allowed_users)
    asset_tool: str | None = None
    # If True, shown but not written by capability save (status only)
    display_only: bool = False


# Primary catalog — order = UI order
CAPABILITY_CATALOG: list[Capability] = [
    Capability(
        id="web_search",
        name="上網查資料",
        description="用搜尋引擎查公開資訊（新聞、資料、價格等）。",
        risk="green",
        risk_label="安全",
        profile_keys=("web_search",),
    ),
    Capability(
        id="web_fetch",
        name="讀取指定網頁",
        description="打開你提供的公開網址，讀取頁面文字（有安全限制）。",
        risk="green",
        risk_label="安全",
        asset_tool="web_fetch",
    ),
    Capability(
        id="files",
        name="讀寫公司文件",
        description="讀取、寫入、搜尋公司工作區裡的檔案。",
        risk="yellow",
        risk_label="要注意",
        profile_keys=("company_file_access",),
    ),
    Capability(
        id="email_draft",
        name="寫 Email 草稿",
        description="只能建立郵件草稿，不能直接寄出（要你自己審核）。",
        risk="yellow",
        risk_label="要注意",
        # Gmail is company asset; status derived from tool availability — display_only
        display_only=True,
    ),
    Capability(
        id="use_tool",
        name="使用公司工具和設備",
        description="使用公司掛載的設備／工具（例如特殊模組）。",
        risk="yellow",
        risk_label="要注意",
        gated_tools=("use_tool",),
    ),
    Capability(
        id="cron",
        name="排程與定時工作",
        description="設定、停止定時任務與相關自動化（含 webhook）。",
        risk="yellow",
        risk_label="要注意",
        gated_tools=(
            "set_cron",
            "stop_cron_job",
            "list_automations",
            "setup_webhook",
            "remove_webhook",
        ),
    ),
    Capability(
        id="notify",
        name="發通知",
        description="向 CEO 發送通知或回報。",
        risk="yellow",
        risk_label="要注意",
        gated_tools=("notify_ceo", "report_to_ceo"),
    ),
    Capability(
        id="bash",
        name="在電腦上執行指令",
        description="可以直接操作系統，只給信任的技術員工。",
        risk="red",
        risk_label="危險",
        gated_tools=("bash",),
    ),
]


def _catalog_gated_tools() -> set[str]:
    tools: set[str] = set()
    for cap in CAPABILITY_CATALOG:
        tools.update(cap.gated_tools)
    return tools


def other_gated_tools() -> tuple[str, ...]:
    """Gated tools not covered by a named capability →「其他」."""
    covered = _catalog_gated_tools()
    return tuple(t for t in GATED_TOOL_NAMES if t not in covered)


OTHER_CAPABILITY = Capability(
    id="other",
    name="其他",
    description="其餘進階技術工具（預算、背景任務、API 金鑰申請等）。",
    risk="yellow",
    risk_label="要注意",
    gated_tools=(),  # filled dynamically
)


def all_capabilities() -> list[Capability]:
    other_tools = other_gated_tools()
    other = Capability(
        id="other",
        name=OTHER_CAPABILITY.name,
        description=OTHER_CAPABILITY.description,
        risk="yellow",
        risk_label="要注意",
        gated_tools=other_tools,
    )
    return list(CAPABILITY_CATALOG) + [other]


# Preset id → label/blurb + capability_id → on|off|inherit
CAPABILITY_PRESETS: dict[str, dict] = {
    "general": {  # 一般員工
        "label": "一般員工",
        "blurb": "上網、文件、郵件草稿；不給指令列與進階自動化。",
        "states": {
            "web_search": "on",
            "web_fetch": "inherit",
            "files": "on",
            "email_draft": "on",
            "use_tool": "off",
            "cron": "off",
            "notify": "off",
            "bash": "off",
            "other": "off",
        },
    },
    "researcher": {  # 研究員
        "label": "研究員",
        "blurb": "適合查資料、讀網頁；不給系統指令。",
        "states": {
            "web_search": "on",
            "web_fetch": "on",
            "files": "on",
            "email_draft": "on",
            "use_tool": "on",
            "cron": "inherit",
            "notify": "inherit",
            "bash": "off",
            "other": "inherit",
        },
    },
    "engineer": {  # 技術員
        "label": "技術員",
        "blurb": "含指令列與排程；請確認對方可信。",
        "states": {
            "web_search": "on",
            "web_fetch": "inherit",
            "files": "on",
            "email_draft": "on",
            "use_tool": "on",
            "cron": "on",
            "notify": "on",
            "bash": "on",
            "other": "on",
        },
    },
}


def presets_public_list() -> list[dict]:
    return [
        {
            "id": pid,
            "label": meta["label"],
            "blurb": meta["blurb"],
            "states": dict(meta["states"]),
        }
        for pid, meta in CAPABILITY_PRESETS.items()
    ]


def capability_public_dict(cap: Capability) -> dict:
    return {
        "id": cap.id,
        "name": cap.name,
        "description": cap.description,
        "risk": cap.risk,
        "risk_label": cap.risk_label,
        "gated_tools": list(cap.gated_tools),
        "profile_keys": list(cap.profile_keys),
        "asset_tool": cap.asset_tool,
        "display_only": cap.display_only,
        "controllable": bool(cap.gated_tools or cap.profile_keys or cap.asset_tool)
        and not cap.display_only,
    }


def aggregate_state(states: list[str]) -> str:
    """Combine per-tool states into on|off|inherit|mixed."""
    if not states:
        return "inherit"
    uniq = set(states)
    if uniq == {"allow"}:
        return "on"
    if uniq == {"deny"}:
        return "off"
    if uniq == {"inherit"}:
        return "inherit"
    # allow mixed with inherit → still treat as mixed for honesty
    return "mixed"


def human_state_label(state: str) -> str:
    return {
        "on": "開",
        "off": "關",
        "inherit": "跟部門一樣",
        "mixed": "部分開啟",
        "allow": "開",
        "deny": "關",
    }.get(state, state)


def apply_capability_states_to_tokens(
    *,
    capability_states: dict[str, str],
    existing_tokens: list[str] | None,
    had_exception: bool,
) -> list[str] | None:
    """Translate capability on/off/inherit into tool_permissions tokens.

    Returns:
      - ``None`` → clear employee exception (all inherit for gated tools we manage)
      - ``list`` → new tool_permissions value

    Only mutates tokens for tools covered by capabilities with gated_tools.
    Unrelated tokens are preserved when possible.
    """
    caps = {c.id: c for c in all_capabilities()}
    grants: set[str] = set()
    denies: set[str] = set()
    if had_exception and existing_tokens is not None:
        from onemancompany.core.permissions import split_permission_tokens
        grants, denies = split_permission_tokens(existing_tokens)
        # Legacy empty list = deny-all gated
        if existing_tokens == []:
            denies = set(GATED_TOOL_NAMES)
            grants = set()

    managed: set[str] = set()
    for cid, state in capability_states.items():
        cap = caps.get(cid)
        if not cap or not cap.gated_tools:
            continue
        managed.update(cap.gated_tools)
        st = state if state in ("on", "off", "inherit") else "inherit"
        for tool in cap.gated_tools:
            grants.discard(tool)
            denies.discard(tool)
            if st == "on":
                grants.add(tool)
            elif st == "off":
                denies.add(tool)
            # inherit: leave both clear

    # Preserve unmanaged gated tokens from previous exception
    if had_exception and existing_tokens:
        from onemancompany.core.permissions import split_permission_tokens
        old_g, old_d = split_permission_tokens(existing_tokens)
        for t in old_g:
            if t not in managed:
                grants.add(t)
        for t in old_d:
            if t not in managed:
                denies.add(t)

    # If everything managed is inherit and nothing left → clear exception
    if not grants and not denies:
        return None

    tokens = sorted(grants) + [f"!{t}" for t in sorted(denies)]
    return tokens


def apply_capability_states_to_profile_keys(
    *,
    capability_states: dict[str, str],
    existing_profile_perms: list[str] | None,
) -> list[str]:
    """Update soft profile.permissions list from capability toggles."""
    perms = set(existing_profile_perms or [])
    caps = {c.id: c for c in all_capabilities()}
    for cid, state in capability_states.items():
        cap = caps.get(cid)
        if not cap or not cap.profile_keys:
            continue
        st = state if state in ("on", "off", "inherit") else "inherit"
        for key in cap.profile_keys:
            if st == "on":
                perms.add(key)
            elif st == "off":
                perms.discard(key)
            # inherit: leave as-is (department soft defaults not modeled)
    return sorted(perms)


def resolve_employee_capability_states(emp_data: dict, employee_id: str) -> dict[str, dict]:
    """Build UI state for each capability without mutating anything."""
    from onemancompany.core.config import (
        PF_DEPARTMENT,
        PF_PERMISSIONS,
        TOOLS_DIR,
        TOOL_YAML_FILENAME,
        read_text_utf,
    )
    from onemancompany.core.permissions import (
        department_allows,
        employee_tool_state,
        is_gated_tool_allowed,
    )
    import yaml

    profile_perms = set(emp_data.get(PF_PERMISSIONS) or [])
    dept = str(emp_data.get(PF_DEPARTMENT) or "General")
    out: dict[str, dict] = {}

    # web_fetch allowed_users
    web_fetch_users: list[str] | None = None
    wf_yaml = TOOLS_DIR / "web_fetch" / TOOL_YAML_FILENAME
    if wf_yaml.exists():
        try:
            conf = yaml.safe_load(read_text_utf(wf_yaml)) or {}
            web_fetch_users = list(conf.get("allowed_users") or [])
        except Exception:
            web_fetch_users = []

    for cap in all_capabilities():
        entry: dict = {
            "id": cap.id,
            "state": "inherit",
            "effective_on": False,
            "dept_effective_on": None,  # bool | None — for「跟部門一樣（目前：開/關）」
            "controllable": bool(cap.gated_tools or cap.profile_keys or cap.asset_tool)
            and not cap.display_only,
            "display_only": cap.display_only,
        }

        if cap.display_only and cap.id == "email_draft":
            entry["state"] = "on"
            entry["effective_on"] = True
            entry["dept_effective_on"] = True
            entry["note"] = "公司郵件草稿工具；不能寄出"
            out[cap.id] = entry
            continue

        if cap.gated_tools:
            tool_states = [employee_tool_state(emp_data, t) for t in cap.gated_tools]
            entry["state"] = aggregate_state(tool_states)
            if entry["state"] == "mixed":
                # Prefer showing off if any deny, else on if any allow
                if any(s == "deny" for s in tool_states):
                    entry["state"] = "off"
                elif any(s == "allow" for s in tool_states):
                    entry["state"] = "on"
                else:
                    entry["state"] = "inherit"
            entry["effective_on"] = any(
                is_gated_tool_allowed(emp_data, t) for t in cap.gated_tools
            )
            entry["dept_effective_on"] = any(
                department_allows(dept, t) for t in cap.gated_tools
            )
            out[cap.id] = entry
            continue

        if cap.profile_keys:
            keys = list(cap.profile_keys)
            if all(k in profile_perms for k in keys):
                entry["state"] = "on"
                entry["effective_on"] = True
            elif not any(k in profile_perms for k in keys):
                entry["state"] = "off"
                entry["effective_on"] = False
            else:
                entry["state"] = "mixed"
                entry["effective_on"] = True
            # Soft profile keys have no department matrix — treat「跟部門」as current on/off
            entry["dept_effective_on"] = entry["effective_on"]
            out[cap.id] = entry
            continue

        if cap.asset_tool == "web_fetch":
            if web_fetch_users is None:
                entry["state"] = "inherit"
                entry["effective_on"] = False
                entry["dept_effective_on"] = False
                entry["note"] = "尚未安裝網頁讀取工具"
            elif not web_fetch_users:
                entry["state"] = "on"
                entry["effective_on"] = True
                entry["dept_effective_on"] = True
                entry["note"] = "開給全員"
            elif employee_id in web_fetch_users:
                entry["state"] = "on"
                entry["effective_on"] = True
                entry["dept_effective_on"] = False
            else:
                entry["state"] = "off"
                entry["effective_on"] = False
                entry["dept_effective_on"] = False
            out[cap.id] = entry
            continue

        out[cap.id] = entry

    return out


def capability_labels_for_effective(emp_data: dict, employee_id: str) -> list[dict]:
    """Read-only tags for employee overview — plain names only for effective-on caps."""
    states = resolve_employee_capability_states(emp_data, employee_id)
    caps = {c.id: c for c in all_capabilities()}
    tags = []
    for cid, st in states.items():
        if not st.get("effective_on"):
            continue
        cap = caps.get(cid)
        if not cap:
            continue
        tags.append({
            "id": cid,
            "name": cap.name,
            "risk": cap.risk,
            "risk_label": cap.risk_label,
        })
    return tags
