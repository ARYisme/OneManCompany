"""Regression: unconstrained path params must not swallow static sibling routes.

FastAPI/Starlette matches routes in registration order. A pattern like
``/api/projects/{project_id}/{iteration_id}`` will match
``/api/projects/x/download`` with ``iteration_id="download"`` if it is
registered before the static ``/download`` route — and then return 404
from an ``iter_\\d+`` guard. Same class of bug for sprint suggest-capacity.
"""

from __future__ import annotations

import re
from pathlib import Path


_ROUTE_RE = re.compile(
    r'@router\.(get|post|put|patch|delete)\("([^"]+)"\)\s*\n(?:async\s+)?def\s+(\w+)',
    re.M,
)


def _routes_from_source() -> list[tuple[str, str, str, int]]:
    text = (Path(__file__).resolve().parents[3] / "src/onemancompany/api/routes.py").read_text(
        encoding="utf-8"
    )
    out: list[tuple[str, str, str, int]] = []
    for m in _ROUTE_RE.finditer(text):
        lineno = text[: m.start()].count("\n") + 1
        out.append((m.group(1).upper(), m.group(2), m.group(3), lineno))
    return out


def _segs(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _is_unconstrained_param(seg: str) -> bool:
    return seg.startswith("{") and seg.endswith("}") and ":" not in seg[1:-1]


def _param_can_match_static(param_path: str, static_path: str) -> bool:
    """True if param_path's pattern can match static_path's concrete segments."""
    a, b = _segs(param_path), _segs(static_path)
    if len(a) != len(b):
        return False
    swallowed_static = False
    for left, right in zip(a, b):
        left_param = left.startswith("{") and left.endswith("}")
        right_param = right.startswith("{") and right.endswith("}")
        if not left_param and not right_param:
            if left != right:
                return False
        elif left_param and not right_param:
            if not _is_unconstrained_param(left):
                return False
            swallowed_static = True
        elif not left_param and right_param:
            return False
    return swallowed_static


def test_no_param_route_registered_before_static_sibling_it_can_swallow():
    routes = _routes_from_source()
    risks: list[str] = []
    for method1, path1, name1, line1 in routes:
        for method2, path2, name2, line2 in routes:
            if method1 != method2 or path1 == path2 or line1 >= line2:
                continue
            if _param_can_match_static(path1, path2):
                risks.append(
                    f"{method1} L{line1} {path1} ({name1}) shadows later "
                    f"L{line2} {path2} ({name2})"
                )
    assert risks == [], "Static routes shadowed by earlier param routes:\n" + "\n".join(risks)


def test_project_static_suffixes_registered_before_iteration_catchall():
    """Explicit guard for the Documents ZIP / lazy-tree failure mode."""
    routes = _routes_from_source()
    by_name = {name: (method, path, line) for method, path, name, line in routes}
    catchall_line = by_name["get_iteration_detail"][2]
    for name in ("list_project_dir", "download_project_workspace", "get_project_tree"):
        assert name in by_name, f"missing route {name}"
        assert by_name[name][2] < catchall_line, (
            f"{name} (L{by_name[name][2]}) must be registered before "
            f"get_iteration_detail (L{catchall_line})"
        )


def test_sprint_suggest_capacity_registered_before_sprint_id():
    routes = _routes_from_source()
    by_name = {name: (method, path, line) for method, path, name, line in routes}
    assert by_name["api_suggest_sprint_capacity"][2] < by_name["api_get_sprint"][2]
