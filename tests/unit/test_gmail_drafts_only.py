"""ARY fork: Gmail tool is drafts-only (docs/ary/email-drafts-only.md)."""

import base64
import email
import importlib.util
import json
from email import policy
from pathlib import Path
from unittest.mock import patch

import pytest

import onemancompany.core.oauth as oauth_mod
from onemancompany.core.oauth import OAuthServiceConfig, complete_oauth_from_redirect, resolve_client_credentials

ROOT = Path(__file__).resolve().parents[2]
GMAIL_DIR = ROOT / "company" / "assets" / "tools" / "gmail"


def _load_gmail():
    spec = importlib.util.spec_from_file_location("gmail_under_test", str(GMAIL_DIR / "gmail.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gmail = _load_gmail()


def test_no_send_tools_exposed():
    from langchain_core.tools import BaseTool
    names = {getattr(gmail, a).name for a in dir(gmail) if isinstance(getattr(gmail, a), BaseTool)}
    assert names == {"gmail_search", "gmail_read", "gmail_read_thread", "gmail_create_draft",
                     "gmail_get_profile", "gmail_list_labels"}


def test_no_send_path_in_source():
    for f in ("gmail.py", "mcp_server.py"):
        src = (GMAIL_DIR / f).read_text()
        assert "messages/send" not in src
        assert "drafts/send" not in src
        assert "def gmail_send" not in src and "def gmail_reply" not in src


@pytest.mark.parametrize("method,path", [
    ("POST", "messages/send"), ("POST", "drafts/send"), ("POST", "drafts/send/"),
    ("POST", "messages"), ("POST", "messages/import"), ("PUT", "drafts/abc"),
    ("DELETE", "messages/abc"), ("POST", "messages/abc/modify"), ("GET", "x/send"),
])
def test_api_request_refuses_send_and_writes(method, path):
    with patch("urllib.request.urlopen") as uo:
        r = gmail._api_request(method, path, body={})
    assert r["status"] == "error" and "drafts-only" in r["message"]
    uo.assert_not_called()


def test_scopes_readonly_compose():
    assert gmail.GMAIL_SCOPES.split() == [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ]


def _decode_raw(raw):
    return email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)


def test_create_reply_draft_utf8_cc_bcc():
    calls = []

    def fake_api(method, path, body=None, params=None):
        calls.append((method, path, body, params))
        if path == "profile":
            return {"emailAddress": "uzena.nari@gmail.com"}
        if path.startswith("messages/"):
            return {"threadId": "T1", "payload": {"headers": [
                {"name": "From", "value": "Client <c@example.com>"},
                {"name": "Subject", "value": "報價"},
                {"name": "Message-ID", "value": "<m2@example.com>"},
                {"name": "References", "value": "<m1@example.com>"},
            ]}}
        if path == "drafts":
            return {"id": "D1", "message": {"id": "M9", "threadId": "T1"}}
        raise AssertionError(path)

    gmail._account_checked = None
    with patch.object(gmail, "_api_request", side_effect=fake_api):
        r = gmail.create_draft_impl(body="您好，附上報價。", cc="a@x.com", bcc="b@x.com",
                                    reply_to_message_id="abc123")
    assert r["status"] == "ok" and r["sent"] is False and r["draft_id"] == "D1"
    assert "ARY" in r["note"] and "草稿" in r["note"]
    post = [c for c in calls if c[0] == "POST"]
    assert len(post) == 1 and post[0][1] == "drafts"
    message = post[0][2]["message"]
    assert message["threadId"] == "T1"
    m = _decode_raw(message["raw"])
    assert m["From"] == "uzena.nari@gmail.com"
    assert m["To"] == "Client <c@example.com>"
    assert m["Cc"] == "a@x.com" and m["Bcc"] == "b@x.com"
    assert m["Subject"] == "Re: 報價"
    assert m["In-Reply-To"] == "<m2@example.com>"
    assert m["References"] == "<m1@example.com> <m2@example.com>"
    assert m.get_content().strip() == "您好，附上報價。"
    assert b"=?utf-8?" in base64.urlsafe_b64decode(message["raw"]).lower()


def test_create_draft_refuses_other_account():
    gmail._account_checked = None
    with patch.object(gmail, "_api_request", return_value={"emailAddress": "someone@else.com"}) as api:
        r = gmail.create_draft_impl(to="x@y.com", subject="s", body="b")
    assert r["status"] == "error" and "uzena.nari@gmail.com" in r["message"]
    assert all(c.args[0] == "GET" for c in api.call_args_list)


CFG = OAuthServiceConfig(service_name="gtest", authorize_url="https://a", token_url="https://t",
                         scopes="s", client_id_env="GT_ID", client_secret_env="GT_SECRET",
                         client_file_env="GT_FILE")


def test_resolve_client_credentials_file(tmp_path, monkeypatch):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "sec"}}))
    monkeypatch.setenv("GT_FILE", str(f))
    monkeypatch.setenv("GT_ID", "envid")
    monkeypatch.setenv("GT_SECRET", "envsec")
    assert resolve_client_credentials(CFG) == ("cid", "sec", "file")
    monkeypatch.setenv("GT_FILE", str(tmp_path / "missing.json"))
    assert resolve_client_credentials(CFG) == ("envid", "envsec", "env")
    monkeypatch.delenv("GT_ID")
    assert resolve_client_credentials(CFG)[2] == ""


def test_paste_redirect_flow(tmp_path, monkeypatch):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "sec"}}))
    monkeypatch.setenv("GT_FILE", str(f))
    monkeypatch.setattr(oauth_mod, "_TOKEN_DIR", tmp_path / "cache")
    oauth_mod._manual_flows.clear()
    oauth_mod._active_flows.clear()
    with patch.object(oauth_mod, "_run_callback_server"), \
         patch("threading.Thread"):
        url = oauth_mod._trigger_oauth_popup(CFG)
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(url).query)["state"][0]

    bad = complete_oauth_from_redirect(CFG, "http://localhost:8585/callback?code=X&state=wrong")
    assert bad["status"] == "error"

    captured = {}

    def fake_post(u, data, timeout=30):
        captured.update(data)
        return 200, {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "scope": "s"}

    with patch.object(oauth_mod, "_http_post", side_effect=fake_post):
        ok = complete_oauth_from_redirect(
            CFG, f"http://localhost:8585/callback?state={state}&code=4%2Fabc&scope=s")
    assert ok["status"] == "ok" and "access_token" not in ok
    assert captured["code"] == "4/abc" and captured["code_verifier"]
    assert captured["redirect_uri"] == "http://localhost:8585/callback"
    cache = json.loads((tmp_path / "cache" / "gtest_tokens.json").read_text())
    assert cache["refresh_token"] == "RT" and "client_secret" not in cache
    # state is single-use
    again = complete_oauth_from_redirect(CFG, f"http://localhost:8585/callback?state={state}&code=Y")
    assert again["status"] == "error"


def test_paste_error_param():
    r = complete_oauth_from_redirect(CFG, "http://localhost:8585/callback?error=access_denied&state=z")
    assert r["status"] == "error" and "access_denied" in r["message"]
