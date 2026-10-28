"""Generic OAuth 2.0 PKCE authorization for tools.

Any tool that needs OAuth can call `ensure_oauth_token(service_config)`.
If no valid token exists, it triggers a popup for CEO authorization,
starts a background callback server, and returns an error for retry.
On next invocation the cached token is used automatically.

Usage from a tool:
    from onemancompany.core.oauth import ensure_oauth_token, OAuthServiceConfig

    ROBLOX = OAuthServiceConfig(
        service_name="roblox",
        authorize_url="https://apis.roblox.com/oauth/v1/authorize",
        token_url="https://apis.roblox.com/oauth/v1/token",
        scopes="openid universe-places:write",
        client_id_env="ROBLOX_OAUTH_CLIENT_ID",
        client_secret_env="ROBLOX_OAUTH_CLIENT_SECRET",
    )

    token = ensure_oauth_token(ROBLOX)
    if token is None:
        return {"status": "auth_required", "message": "OAuth popup sent to CEO. Retry shortly."}
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

# Avoid importing heavy deps at module level
from loguru import logger
from onemancompany.core.config import ASSETS_DIR as _ASSETS_DIR, ENCODING_UTF8, SYSTEM_AGENT, read_text_utf, write_text_utf
_TOKEN_DIR = _ASSETS_DIR / ".oauth_cache"

# Track active authorization flows to avoid duplicate popups
_active_flows: dict[str, float] = {}  # service_name -> deadline
_flow_lock = threading.Lock()

# Pending flows that can be completed by pasting the redirect URL (remote use,
# when the browser can't reach the container's localhost callback).
# state -> {"service_name", "verifier", "config", "deadline"}
_manual_flows: dict[str, dict] = {}
MANUAL_FLOW_TTL = 600  # seconds


# ---------------------------------------------------------------------------
# Snapshot provider — persist OAuth flow state across graceful restarts
# ---------------------------------------------------------------------------
from onemancompany.core.snapshot import snapshot_provider


@snapshot_provider("oauth_flows")
class _OAuthFlowsSnapshot:
    @staticmethod
    def save() -> dict:
        now = time.time()
        # Only save flows that haven't expired yet
        active = {k: v for k, v in _active_flows.items() if v > now}
        pending = {k: v for k, v in _pending_credentials.items() if v > now}
        if not active and not pending:
            return {}
        return {"active_flows": active, "pending_credentials": pending}

    @staticmethod
    def restore(data: dict) -> None:
        now = time.time()
        for k, v in data.get("active_flows", {}).items():
            if v > now:
                _active_flows[k] = v
        for k, v in data.get("pending_credentials", {}).items():
            if v > now:
                _pending_credentials[k] = v


@dataclass
class OAuthServiceConfig:
    """Configuration for an OAuth 2.0 service."""
    service_name: str              # e.g. "roblox", "github"
    authorize_url: str             # Authorization endpoint
    token_url: str                 # Token endpoint
    scopes: str = ""               # Space-separated scopes
    client_id_env: str = ""        # Env var name for client_id
    client_secret_env: str = ""    # Env var name for client_secret
    redirect_port: int = 8585      # Local callback port
    token_lifetime_buffer: int = 60  # Seconds before expiry to refresh
    client_file_env: str = ""      # Env var naming a JSON file with client_id/secret
                                   # (e.g. a read-only mounted secret; Google's
                                   # downloaded client JSON is accepted as-is)


def resolve_client_credentials(config: OAuthServiceConfig) -> tuple[str, str, str]:
    """Return (client_id, client_secret, source) for *config*.

    Order: the JSON file named by ``config.client_file_env`` (if set and
    readable), then the ``client_id_env`` / ``client_secret_env`` env vars.
    ``source`` is "file", "env" or "" (not configured). Values are never logged.
    """
    file_env = getattr(config, "client_file_env", "") or ""
    path = os.environ.get(file_env, "") if file_env else ""
    if path:
        try:
            data = json.loads(Path(path).read_text(encoding=ENCODING_UTF8))
            if isinstance(data, dict):
                inner = data.get("installed") or data.get("web") or data
                cid = str(inner.get("client_id", "") or "")
                csec = str(inner.get("client_secret", "") or "")
                if cid and csec:
                    return cid, csec, "file"
        except Exception as exc:  # unreadable / not JSON — fall back to env
            logger.warning("[oauth] Client file for {} unreadable: {}",
                           config.service_name, type(exc).__name__)
    cid = os.environ.get(config.client_id_env, "") if config.client_id_env else ""
    csec = os.environ.get(config.client_secret_env, "") if config.client_secret_env else ""
    if cid and csec:
        return cid, csec, "env"
    return cid, csec, ""


def _token_cache_path(service_name: str) -> Path:
    _TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    return _TOKEN_DIR / f"{service_name}_tokens.json"


def _load_tokens(service_name: str) -> dict:
    path = _token_cache_path(service_name)
    if path.exists():
        try:
            return json.loads(read_text_utf(path))
        except Exception:
            return {}
    return {}


def _save_tokens(service_name: str, data: dict) -> None:
    path = _token_cache_path(service_name)
    write_text_utf(path, json.dumps(data, indent=2))
    logger.debug("[oauth] Saved tokens to {}", path)


def _generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _http_post(url: str, data: dict, timeout: int = 30) -> tuple[int, dict]:
    """POST form-encoded data via urllib (no dependencies)."""
    import urllib.request
    import urllib.error

    encoded = urlencode(data).encode(ENCODING_UTF8)
    req = urllib.request.Request(
        url, data=encoded, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw[:2000]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:2000]}


# ── Token refresh ────────────────────────────────────────

def _refresh_token(config: OAuthServiceConfig) -> dict | None:
    """Try to refresh access token using stored refresh_token."""
    cache = _load_tokens(config.service_name)
    refresh_token = cache.get("refresh_token", "")
    r_id, r_secret, r_source = resolve_client_credentials(config)
    if r_source == "file":
        client_id, client_secret = r_id, r_secret
    else:
        client_id = cache.get("client_id", "") or r_id
        client_secret = cache.get("client_secret", "") or r_secret

    if not refresh_token or not client_id or not client_secret:
        return None

    status, body = _http_post(config.token_url, {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    })

    if status != 200:
        return None

    cache.update({
        "access_token": body.get("access_token", ""),
        "refresh_token": body.get("refresh_token", refresh_token),
        "expires_at": time.time() + body.get("expires_in", 900) - config.token_lifetime_buffer,
        "scope": body.get("scope", cache.get("scope", "")),
    })
    if r_source == "file":
        # Client secret lives in the mounted secret file — don't copy it into the cache
        cache.pop("client_id", None)
        cache.pop("client_secret", None)
    else:
        cache.update({"client_id": client_id, "client_secret": client_secret})
    _save_tokens(config.service_name, cache)
    return cache


# ── Get valid token ──────────────────────────────────────

def get_oauth_token(config: OAuthServiceConfig) -> str | None:
    """Get a valid access token for the service, auto-refreshing if needed.

    Returns the token string, or None if unavailable.
    Does NOT trigger authorization flow — use ensure_oauth_token() for that.
    """
    cache = _load_tokens(config.service_name)

    # Valid cached token
    if cache.get("access_token") and cache.get("expires_at", 0) > time.time():
        return cache["access_token"]

    # Try refresh
    result = _refresh_token(config)
    if result and result.get("access_token"):
        return result["access_token"]

    return None


def get_oauth_header(config: OAuthServiceConfig) -> dict:
    """Get auth header dict, e.g. {"Authorization": "Bearer xxx"}."""
    token = get_oauth_token(config)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── Authorization flow with popup ────────────────────────

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Captures OAuth callback code."""
    auth_code: str | None = None
    _config: OAuthServiceConfig | None = None
    _verifier: str = ""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful!</h2>"
                             b"<p>You can close this tab.</p>")
            # Exchange code for tokens immediately
            if self._config:
                result = _exchange_code(
                    self._config, self.auth_code, self._verifier
                )
                if result.get("error"):
                    logger.error("[oauth] Token exchange failed: {}", result)
                else:
                    logger.info("[oauth] Token exchange succeeded for {}", self._config.service_name)
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h2>Authorization failed: {error}</h2>".encode())

    def log_message(self, format, *args):
        pass


def _exchange_code(config: OAuthServiceConfig, code: str, verifier: str) -> dict:
    """Exchange authorization code for tokens."""
    client_id, client_secret, source = resolve_client_credentials(config)
    redirect_uri = f"http://localhost:{config.redirect_port}/callback"

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
    if verifier:
        data["code_verifier"] = verifier

    status, body = _http_post(config.token_url, data)
    if status != 200:
        return {"error": f"Token exchange failed (HTTP {status})", "detail": body}

    cache = {
        "access_token": body.get("access_token", ""),
        "refresh_token": body.get("refresh_token", ""),
        "expires_at": time.time() + body.get("expires_in", 900) - config.token_lifetime_buffer,
        "scope": body.get("scope", ""),
    }
    if source != "file":
        cache["client_id"] = client_id
        cache["client_secret"] = client_secret
    _save_tokens(config.service_name, cache)

    # Clear active flow
    with _flow_lock:
        _active_flows.pop(config.service_name, None)

    return cache


def _run_callback_server(config: OAuthServiceConfig, verifier: str):
    """Run callback server in background thread, waiting up to 2 min."""
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler._config = config
    _OAuthCallbackHandler._verifier = verifier

    try:
        server = HTTPServer(("localhost", config.redirect_port), _OAuthCallbackHandler)
    except OSError:
        # Port already in use — another flow is running
        return

    server.timeout = 120
    deadline = time.time() + 120
    while _OAuthCallbackHandler.auth_code is None and time.time() < deadline:
        server.handle_request()
    server.server_close()

    with _flow_lock:
        _active_flows.pop(config.service_name, None)


def _trigger_oauth_popup(config: OAuthServiceConfig) -> str:
    """Start OAuth flow: callback server + popup event. Returns auth_url."""
    client_id, _secret, _source = resolve_client_credentials(config)
    if not client_id:
        return ""

    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)
    redirect_uri = f"http://localhost:{config.redirect_port}/callback"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": config.scopes,
        "response_type": "code",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{config.authorize_url}?{urlencode(auth_params)}"

    # Mark flow as active
    with _flow_lock:
        _active_flows[config.service_name] = time.time() + 120
        # Remote / headless use: remember the PKCE verifier so the CEO can paste
        # the redirect URL (or code) back via complete_oauth_from_redirect().
        _manual_flows[state] = {
            "service_name": config.service_name,
            "verifier": verifier,
            "config": config,
            "deadline": time.time() + MANUAL_FLOW_TTL,
        }

    # Start callback server in background
    t = threading.Thread(
        target=_run_callback_server, args=(config, verifier),
        daemon=True, name=f"oauth-{config.service_name}",
    )
    t.start()

    # Publish popup to frontend
    try:
        import asyncio
        from onemancompany.core.events import open_popup
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                open_popup(
                    title=f"{config.service_name.title()} Authorization Required",
                    message=f"The {config.service_name.title()} tool needs authorization.\n"
                            f"Click 'Authorize' to log in and grant access.",
                    popup_type="oauth",
                    url=auth_url,
                    agent=SYSTEM_AGENT,
                ),
                loop,
            )
    except Exception as e:
        from loguru import logger as _logger
        _logger.debug("OAuth popup event publish failed: {}", e)

    return auth_url


def ensure_oauth_token(config: OAuthServiceConfig) -> str | None:
    """Get a valid OAuth token, triggering authorization popup if needed.

    Returns:
        - Token string if available
        - None if authorization is needed (popup has been sent to CEO)

    The tool should return an "auth_required" response when None is returned.
    On next invocation, the token will be available after CEO authorizes.
    """
    # Try cached/refreshed token first
    token = get_oauth_token(config)
    if token:
        return token

    # Check if client credentials are configured
    client_id, client_secret, _source = resolve_client_credentials(config)
    if not client_id or not client_secret:
        return None  # Can't do OAuth without credentials

    # Check if a flow is already active
    with _flow_lock:
        if config.service_name in _active_flows:
            if _active_flows[config.service_name] > time.time():
                return None  # Flow in progress, don't trigger another popup

    # Trigger new authorization flow
    _trigger_oauth_popup(config)
    return None


# ── Remote completion: paste the redirect URL ─────────────

def complete_oauth_from_redirect(config: OAuthServiceConfig, pasted: str) -> dict:
    """Finish an OAuth flow from a pasted redirect URL (or bare code).

    For remote setups: the provider redirects the CEO's browser to
    ``http://localhost:<port>/callback?code=...&state=...``, which fails to load
    because the callback server only listens inside the container. The CEO
    copies the full URL from the address bar and pastes it into the OMC UI;
    the code is exchanged here, inside the container, with the stored PKCE
    verifier. The ``state`` must match a pending flow for this service.

    Returns {"status": "ok"|"error", "message": ...}; never returns tokens.
    """
    text = (pasted or "").strip()
    if not text:
        return {"status": "error", "message": "Nothing pasted."}

    code = state = err = ""
    if "code=" in text or "error=" in text or text.startswith("http"):
        query = urlparse(text).query if "://" in text else text.lstrip("?")
        params = parse_qs(query)
        code = (params.get("code") or [""])[0]
        state = (params.get("state") or [""])[0]
        err = (params.get("error") or [""])[0]
    else:
        code = text
    if err:
        return {"status": "error", "message": f"Authorization was denied or failed: {err}"}
    if not code:
        return {"status": "error", "message": "No authorization code found in the pasted text."}

    now = time.time()
    with _flow_lock:
        for k in [k for k, v in _manual_flows.items() if v["deadline"] <= now]:
            _manual_flows.pop(k, None)
        if state:
            flow = _manual_flows.get(state)
            if not flow or flow["service_name"] != config.service_name:
                return {"status": "error",
                        "message": "Unknown or expired login session (state mismatch). Click Login again."}
        else:
            candidates = [(k, v) for k, v in _manual_flows.items()
                          if v["service_name"] == config.service_name]
            if not candidates:
                return {"status": "error", "message": "No pending login. Click Login first."}
            state, flow = max(candidates, key=lambda kv: kv[1]["deadline"])
        _manual_flows.pop(state, None)

    result = _exchange_code(config, code, flow["verifier"])
    if result.get("error"):
        logger.error("[oauth] Manual token exchange failed for {}", config.service_name)
        detail = result.get("detail") or {}
        reason = detail.get("error_description") or detail.get("error") or result["error"]
        return {"status": "error", "message": f"Token exchange failed: {reason}"}
    logger.info("[oauth] Manual token exchange succeeded for {}", config.service_name)
    return {"status": "ok", "message": f"{config.service_name} authorized",
            "scope": result.get("scope", "")}


# ── Generic credential request (non-OAuth) ───────────────

# Tracks which services have pending credential requests
_pending_credentials: dict[str, float] = {}  # service -> deadline


def request_credentials(
    service_name: str,
    title: str,
    message: str = "",
    fields: list[dict] | None = None,
) -> bool:
    """Request credentials from CEO via popup. Returns True if popup was sent.

    Use this when a tool needs an API key, password, or other credentials
    that the user must provide through the UI.

    Args:
        service_name: Unique identifier (e.g. "roblox", "openai").
            Credentials are stored as env vars: SERVICENAME_FIELDNAME.
        title: Popup title shown to CEO.
        message: Explanation text.
        fields: List of field dicts:
            [{"name": "api_key", "label": "API Key", "secret": True, "placeholder": "sk-..."}]
            If not provided, defaults to a single "api_key" field.

    Returns:
        True if popup was sent, False if a request is already pending.
    """
    if fields is None:
        fields = [{"name": "api_key", "label": "API Key", "secret": True}]

    with _flow_lock:
        if service_name in _pending_credentials:
            if _pending_credentials[service_name] > time.time():
                return False  # Already pending
        _pending_credentials[service_name] = time.time() + 120

    try:
        import asyncio
        from onemancompany.core.events import event_bus, CompanyEvent
        from onemancompany.core.models import EventType
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                event_bus.publish(CompanyEvent(
                    type=EventType.REQUEST_CREDENTIALS,
                    payload={
                        "service_name": service_name,
                        "title": title,
                        "message": message,
                        "fields": fields,
                    },
                    agent=SYSTEM_AGENT,
                )),
                loop,
            )
            return True
    except Exception as e:
        from loguru import logger as _logger
        _logger.debug("Credential request event publish failed: {}", e)

    return False
