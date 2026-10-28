"""Gmail MCP server (ARY fork: drafts-only) — exposes Gmail tools to
self-hosted Claude CLI employees.

Runs as a stdio subprocess. All logic (OAuth, HTTP, the drafts-only guard)
lives in the sibling gmail.py; this file only wraps it, so both entry points
behave identically. There is NO send / reply-and-send tool here.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_spec = importlib.util.spec_from_file_location(
    "asset_tool_gmail_impl", str(Path(__file__).with_name("gmail.py")))
_gmail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gmail)

mcp = FastMCP("gmail")


def _dump(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def gmail_search(query: str, max_results: int = 10) -> str:
    """Search Gmail messages in uzena.nari@gmail.com (read-only).

    Args:
        query: Gmail search query (same syntax as Gmail search box).
        max_results: Maximum number of results (default 10, max 50).
    """
    return _dump(_gmail.search_impl(query, max_results))


@mcp.tool()
def gmail_read(message_id: str) -> str:
    """Read a specific Gmail message by ID (read-only).

    Args:
        message_id: The Gmail message ID.
    """
    return _dump(_gmail.read_impl(message_id))


@mcp.tool()
def gmail_read_thread(thread_id: str) -> str:
    """Read all messages in a Gmail thread (read-only).

    Args:
        thread_id: The Gmail thread ID.
    """
    return _dump(_gmail.read_thread_impl(thread_id))


@mcp.tool()
def gmail_create_draft(to: str = "", subject: str = "", body: str = "", cc: str = "",
                       bcc: str = "", reply_to_message_id: str = "") -> str:
    """Create a Gmail DRAFT in uzena.nari@gmail.com. It is NEVER sent.

    You cannot send email. ARY reviews every draft and sends it himself.
    After creating a draft, ALWAYS tell ARY (report_to_ceo) that a draft is
    waiting (recipient + subject). From is always uzena.nari@gmail.com.

    Args:
        to: Recipient address(es), comma-separated. Optional when replying.
        subject: Subject line (UTF-8). Optional when replying ("Re: ...").
        body: Plain-text body (UTF-8).
        cc: CC recipients (optional).
        bcc: BCC recipients (optional).
        reply_to_message_id: Gmail message ID to reply to (optional); keeps the thread.
    """
    return _dump(_gmail.create_draft_impl(to, subject, body, cc, bcc, "", reply_to_message_id))


@mcp.tool()
def gmail_get_profile() -> str:
    """Get the authorized Gmail account's profile (should be uzena.nari@gmail.com)."""
    return _dump(_gmail.get_profile_impl())


@mcp.tool()
def gmail_list_labels() -> str:
    """List all Gmail labels (folders/categories)."""
    return _dump(_gmail.list_labels_impl())


# ── Entry point ────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
