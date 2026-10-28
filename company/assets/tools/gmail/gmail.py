"""Gmail tool (ARY fork: drafts-only) — pure HTTP + OAuth, no SDK dependency.

Provides LangChain @tool functions for searching and reading email and for
creating Gmail DRAFTS via the Gmail REST API.

DRAFTS-ONLY GUARANTEE (ARY fork, see docs/ary/email-drafts-only.md):
  * There is no send / reply-and-send tool. This module never calls
    ``messages.send`` or ``drafts.send``.
  * ``_api_request`` refuses any path that ends in ``send`` and only allows
    POST to ``drafts`` — so even a future helper cannot send by mistake.
  * The OAuth scopes are gmail.readonly + gmail.compose. NOTE: gmail.compose
    technically permits sending, so the no-send guarantee comes from this
    code, not from the scope.
  * Every draft is created in uzena.nari@gmail.com's Drafts folder with
    ``From: uzena.nari@gmail.com``. ARY reviews and sends it himself.

Auth: core.oauth OAuthServiceConfig with Google OAuth 2.0. Client ID/secret
come from the env vars or from the JSON file named by GOOGLE_OAUTH_CLIENT_FILE
(mounted read-only secret). On first call, a popup asks the CEO to authorize.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.policy import default as _default_policy
from urllib.parse import quote, urlencode

from langchain_core.tools import tool

# ── Constants ──────────────────────────────────────────

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# The ONLY mailbox OMC employees may draft from (ARY decision 2026-10-28).
DRAFT_ACCOUNT = "uzena.nari@gmail.com"

GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.compose"
)

DRAFT_NOTE_ZH = (
    "草稿已存到 uzena.nari@gmail.com 的 Gmail「草稿」匣，尚未寄出。"
    "請 ARY 親自打開 Gmail 檢查內容後自己按「傳送」；員工沒有寄信功能，也不能代寄。"
    "請用 report_to_ceo() 告訴 ARY 有一封草稿在等他審核（附上收件人和主旨）。"
)

DRAFTS_URL = f"https://mail.google.com/mail/u/?authuser={DRAFT_ACCOUNT}#drafts"


# ── OAuth config ───────────────────────────────────────

def _gmail_oauth_config():
    """Lazy-load Gmail OAuth config."""
    try:
        from onemancompany.core.oauth import OAuthServiceConfig
        kwargs = dict(
            service_name="gmail",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=GMAIL_SCOPES,
            client_id_env="GOOGLE_OAUTH_CLIENT_ID",
            client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
        )
        try:
            return OAuthServiceConfig(client_file_env="GOOGLE_OAUTH_CLIENT_FILE", **kwargs)
        except TypeError:
            # Older core.oauth without client_file_env support
            return OAuthServiceConfig(**kwargs)
    except ImportError:
        return None


def _get_auth_header() -> tuple[dict, str | None]:
    """Get OAuth auth header for Gmail API.

    Returns (headers_dict, error_message).
    """
    config = _gmail_oauth_config()
    if not config:
        return {}, "OAuth module not available"

    from onemancompany.core.oauth import ensure_oauth_token
    token = ensure_oauth_token(config)
    if token is None:
        return {}, ("Gmail OAuth authorization required. A popup has been sent to CEO. "
                    "（Gmail 尚未授權：請 ARY 在 OMC 工具頁的 Gmail 完成授權。）")

    return {"Authorization": f"Bearer {token}"}, None


def _is_forbidden(method: str, path: str) -> bool:
    """Defense in depth: nothing in this tool may ever send mail."""
    p = path.split("?", 1)[0].rstrip("/").lower()
    if p.endswith("send") or "/send" in p:
        return True
    if method.upper() not in ("GET", "POST"):
        return True
    if method.upper() == "POST" and p != "drafts":
        return True
    return False


def _api_request(method: str, path: str, body: dict | None = None,
                 params: dict | None = None) -> dict:
    """Make a Gmail API request (GET anything read-only, POST only to drafts)."""
    if _is_forbidden(method, path):
        return {"status": "error",
                "message": "Refused: this Gmail tool is drafts-only and cannot send mail."}

    auth, err = _get_auth_header()
    if err:
        return {"status": "error", "message": err}

    url = f"{_GMAIL_API}/{path}"
    if params:
        url += "?" + urlencode(params, doseq=True)

    data = json.dumps(body).encode() if body else None
    headers = {**auth, "Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        return {"status": "error", "code": e.code, "message": body_text[:500]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _is_error(result: dict) -> bool:
    return "error" in str(result.get("status", ""))


# ── Helper functions ────────────────────────────────────

def _decode_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        if mime.startswith("multipart/") and part.get("parts"):
            result = _decode_body(part)
            if result:
                return result

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            return "[HTML] " + base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")[:2000]

    return ""


def _get_header(headers: list[dict], name: str) -> str:
    """Get a header value by name."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _format_message(msg: dict) -> dict:
    """Format a Gmail message into a readable dict."""
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    return {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "cc": _get_header(headers, "Cc"),
        "subject": _get_header(headers, "Subject"),
        "date": _get_header(headers, "Date"),
        "message_id_header": _get_header(headers, "Message-ID"),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
        "body": _decode_body(payload),
    }


_account_checked: str | None = None


def _check_account() -> str | None:
    """Make sure the authorized Gmail account is DRAFT_ACCOUNT. Returns error or None."""
    global _account_checked
    if _account_checked == DRAFT_ACCOUNT:
        return None
    prof = _api_request("GET", "profile")
    if _is_error(prof):
        return prof.get("message", "Gmail profile check failed")
    email = (prof.get("emailAddress") or "").lower()
    if email != DRAFT_ACCOUNT:
        return (f"Refused: Gmail is authorized as {email or '?'}, but OMC may only draft from "
                f"{DRAFT_ACCOUNT}. 請 ARY 在 OMC 工具頁 Gmail 按 Disconnect，再用 {DRAFT_ACCOUNT} 重新授權。")
    _account_checked = email
    return None


def build_draft_message(to: str, subject: str, body: str, cc: str = "", bcc: str = "",
                        attachments: str = "", in_reply_to: str = "",
                        references: str = "") -> dict:
    """Build a UTF-8 MIME message (From fixed to DRAFT_ACCOUNT).

    Returns {"msg": EmailMessage, "attached": [...], "missing": [...]}.
    Non-ASCII subjects / display names are RFC 2047 encoded; the body is
    UTF-8 (base64 transfer encoding).
    """
    msg = EmailMessage(policy=_default_policy)
    msg["From"] = DRAFT_ACCOUNT
    if to:
        msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject or ""
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body or "", subtype="plain", charset="utf-8", cte="base64")

    attached, missing = [], []
    attach_paths = [p.strip() for p in attachments.split(",") if p.strip()] if attachments else []
    for fpath in attach_paths:
        if not os.path.isfile(fpath):
            missing.append(fpath)
            continue
        ctype, _ = mimetypes.guess_type(fpath)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(fpath, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(fpath))
        attached.append(fpath)
    return {"msg": msg, "attached": attached, "missing": missing}


def create_draft_impl(to: str = "", subject: str = "", body: str = "", cc: str = "",
                      bcc: str = "", attachments: str = "",
                      reply_to_message_id: str = "") -> dict:
    """Shared implementation for the LangChain tool and the MCP server."""
    err = _check_account()
    if err:
        return {"status": "error", "message": err}

    thread_id = ""
    in_reply_to = ""
    references = ""
    if reply_to_message_id:
        original = _api_request(
            "GET", f"messages/{quote(reply_to_message_id, safe='')}",
            params={"format": "metadata",
                    "metadataHeaders": ["From", "Reply-To", "To", "Subject", "Message-ID", "References"]})
        if _is_error(original):
            return original
        headers = original.get("payload", {}).get("headers", [])
        thread_id = original.get("threadId", "")
        in_reply_to = _get_header(headers, "Message-ID")
        old_refs = _get_header(headers, "References")
        references = f"{old_refs} {in_reply_to}".strip() if in_reply_to else old_refs
        if not to:
            to = _get_header(headers, "Reply-To") or _get_header(headers, "From")
        if not subject:
            orig_subject = _get_header(headers, "Subject")
            subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

    if not to:
        return {"status": "error", "message": "Missing recipient (to)."}

    built = build_draft_message(to, subject, body, cc, bcc, attachments, in_reply_to, references)
    raw = base64.urlsafe_b64encode(built["msg"].as_bytes()).decode("ascii")
    message: dict = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id
    result = _api_request("POST", "drafts", body={"message": message})
    if _is_error(result):
        return result

    resp = {
        "status": "ok",
        "sent": False,
        "draft_id": result.get("id", ""),
        "message_id": result.get("message", {}).get("id", ""),
        "thread_id": result.get("message", {}).get("threadId", thread_id),
        "from": DRAFT_ACCOUNT,
        "to": to,
        "subject": subject,
        "drafts_url": DRAFTS_URL,
        "note": DRAFT_NOTE_ZH,
    }
    if built["attached"]:
        resp["attachments"] = built["attached"]
    if built["missing"]:
        resp["attachments_missing"] = built["missing"]
        resp["warning"] = f"These files were not found and NOT attached: {built['missing']}"
    return resp


def search_impl(query: str, max_results: int = 10) -> dict:
    max_results = max(1, min(int(max_results or 10), 50))
    result = _api_request("GET", "messages", params={"q": query, "maxResults": max_results})
    if _is_error(result):
        return result
    messages = result.get("messages", [])
    detailed = []
    for msg_ref in messages[:max_results]:
        msg = _api_request("GET", f"messages/{msg_ref['id']}", params={
            "format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]})
        if not _is_error(msg):
            headers = msg.get("payload", {}).get("headers", [])
            detailed.append({
                "id": msg.get("id", ""),
                "thread_id": msg.get("threadId", ""),
                "from": _get_header(headers, "From"),
                "to": _get_header(headers, "To"),
                "subject": _get_header(headers, "Subject"),
                "date": _get_header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
            })
    return {"status": "ok", "count": len(detailed), "messages": detailed}


def read_impl(message_id: str) -> dict:
    result = _api_request("GET", f"messages/{quote(message_id, safe='')}", params={"format": "full"})
    if _is_error(result):
        return result
    return {"status": "ok", "message": _format_message(result)}


def read_thread_impl(thread_id: str) -> dict:
    result = _api_request("GET", f"threads/{quote(thread_id, safe='')}", params={"format": "full"})
    if _is_error(result):
        return result
    messages = [_format_message(m) for m in result.get("messages", [])]
    return {"status": "ok", "thread_id": thread_id, "message_count": len(messages), "messages": messages}


def get_profile_impl() -> dict:
    result = _api_request("GET", "profile")
    if _is_error(result):
        return result
    return {
        "status": "ok",
        "email": result.get("emailAddress", ""),
        "total_messages": result.get("messagesTotal", 0),
        "total_threads": result.get("threadsTotal", 0),
        "drafts_only": True,
    }


def list_labels_impl() -> dict:
    result = _api_request("GET", "labels")
    if _is_error(result):
        return result
    labels = [{"id": lb["id"], "name": lb["name"], "type": lb.get("type", "")}
              for lb in result.get("labels", [])]
    return {"status": "ok", "labels": labels}


# ── LangChain Tools ────────────────────────────────────

@tool
def gmail_search(query: str, max_results: int = 10) -> dict:
    """Search Gmail messages in uzena.nari@gmail.com (read-only).

    Args:
        query: Gmail search query (same syntax as Gmail search box).
               Examples: "from:user@example.com", "subject:meeting", "is:unread",
               "after:2024/01/01", "has:attachment"
        max_results: Maximum number of results to return (default 10, max 50).
    """
    return search_impl(query, max_results)


@tool
def gmail_read(message_id: str) -> dict:
    """Read a specific Gmail message by ID (read-only).

    Args:
        message_id: The Gmail message ID (from gmail_search results).
    """
    return read_impl(message_id)


@tool
def gmail_read_thread(thread_id: str) -> dict:
    """Read all messages in a Gmail thread (read-only).

    Args:
        thread_id: The Gmail thread ID (from gmail_search results).
    """
    return read_thread_impl(thread_id)


@tool
def gmail_create_draft(to: str = "", subject: str = "", body: str = "", cc: str = "",
                       bcc: str = "", attachments: str = "",
                       reply_to_message_id: str = "") -> dict:
    """Create a Gmail DRAFT in uzena.nari@gmail.com. It is NEVER sent.

    You cannot send email. ARY reviews every draft and sends it himself.
    After creating a draft, ALWAYS tell ARY with report_to_ceo() that a draft
    is waiting (recipient + subject). From is always uzena.nari@gmail.com.

    Args:
        to: Recipient address(es), comma-separated. Optional when replying
            (defaults to the original sender / Reply-To).
        subject: Subject line (UTF-8, Chinese OK). Optional when replying
                 (defaults to "Re: <original subject>").
        body: Plain-text body (UTF-8, Chinese OK).
        cc: CC recipients, comma-separated (optional).
        bcc: BCC recipients, comma-separated (optional).
        attachments: Comma-separated absolute file paths to attach (optional).
        reply_to_message_id: Gmail message ID to reply to (optional). The draft is
            placed in the same thread with In-Reply-To / References headers.
    """
    return create_draft_impl(to, subject, body, cc, bcc, attachments, reply_to_message_id)


@tool
def gmail_get_profile() -> dict:
    """Get the authorized Gmail account's profile (should be uzena.nari@gmail.com)."""
    return get_profile_impl()


@tool
def gmail_list_labels() -> dict:
    """List all Gmail labels (folders/categories)."""
    return list_labels_impl()
