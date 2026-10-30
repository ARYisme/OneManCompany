"""API tests for Permission Center endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _app():
    from onemancompany.api.routes import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_get_permissions_matrix():
    snapshot = {
        "gated_tools": ["bash", "use_tool"],
        "departments": {"General": []},
        "department_order": ["General"],
        "employees": [],
        "audit": [],
    }
    with patch(
        "onemancompany.core.permissions.build_permissions_snapshot",
        return_value=snapshot,
    ):
        transport = ASGITransport(app=_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/permissions")
    assert resp.status_code == 200
    assert resp.json()["gated_tools"] == ["bash", "use_tool"]


@pytest.mark.asyncio
async def test_put_departments():
    with patch(
        "onemancompany.core.permissions.save_department_defaults",
        return_value={"Engineering": ["bash"]},
    ) as save:
        transport = ASGITransport(app=_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/permissions/departments",
                json={"departments": {"Engineering": ["bash"]}, "actor_id": "ceo"},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    save.assert_called_once()


@pytest.mark.asyncio
async def test_put_employee_permissions():
    with patch(
        "onemancompany.core.permissions.set_employee_permissions",
        new_callable=AsyncMock,
        return_value=["bash", "!use_tool"],
    ):
        transport = ASGITransport(app=_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/permissions/employee/00006",
                json={"tool_permissions": ["bash", "!use_tool"]},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["employee_id"] == "00006"
    assert "!use_tool" in body["tool_permissions"]


@pytest.mark.asyncio
async def test_delete_employee_exception():
    with patch(
        "onemancompany.core.permissions.clear_employee_exception",
        new_callable=AsyncMock,
    ) as clear:
        transport = ASGITransport(app=_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/permissions/employee/00006?actor_id=ceo")
    assert resp.status_code == 200
    clear.assert_awaited()
