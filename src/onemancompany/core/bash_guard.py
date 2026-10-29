"""Guard employee bash / file tools away from secrets and Gmail API bypass.

Policy (ARY 2026-10-29, option D):
- Employees keep official Gmail tools (read / create draft only).
- bash must not read OAuth/token/secret files or call Gmail HTTP APIs.
- When the main process is root, bash subprocess drops to nobody (65534)
  so mode-600 secret files are unreadable even if a command slips through.

Disable privilege drop only with OMC_BASH_DROP_PRIVS=0 (emergency / local debug).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Substrings / regexes that indicate secret paths or Gmail API abuse in a shell command.
_CMD_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\.oauth_cache",
        r"gmail_tokens",
        r"/run/secrets",
        r"google_oauth_client",
        r"crawl4ai_api_token",
        r"client_secret_.*\.json",
        r"gmail\.googleapis\.com",
        r"www\.googleapis\.com/gmail",
        r"googleapis\.com/upload/gmail",
        r"oauth2\.googleapis\.com/token",
        r"drafts/send",
        r"messages/send",
        r"/gmail/v1/",
        r"gmail_delete\.py",
    )
)

_ENV_BLOCK_SUBSTR = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "API_KEY",
    "CREDENTIAL",
    "OMC_UI_PASSWORD",
)

_SENSITIVE_NAME_PARTS = (
    ".oauth_cache",
    "gmail_tokens",
    "google_oauth_client",
    "crawl4ai_api_token",
)


def _sensitive_roots() -> list[Path]:
    roots: list[Path] = [Path("/run/secrets")]
    try:
        from onemancompany.core.config import ASSETS_DIR, DATA_ROOT

        roots.append((ASSETS_DIR / ".oauth_cache").resolve())
        roots.append((DATA_ROOT / ".env").resolve())
    except Exception:
        pass
    return roots


def is_sensitive_path(path: str | Path | None) -> bool:
    """True if path is a secret/token location employees must not touch."""
    if path is None:
        return False
    try:
        resolved = Path(path).expanduser().resolve()
    except Exception:
        text = str(path).lower()
        return any(part in text for part in _SENSITIVE_NAME_PARTS)

    text = str(resolved).lower()
    if any(part in text for part in _SENSITIVE_NAME_PARTS):
        return True

    for root in _sensitive_roots():
        try:
            root_res = root.resolve()
        except Exception:
            root_res = root
        if resolved == root_res or str(resolved).startswith(str(root_res) + os.sep):
            return True
    return False


def check_bash_command(command: str) -> str | None:
    """Return an error message if the shell command is blocked; else None."""
    if not command or not str(command).strip():
        return "Empty bash command."
    for pat in _CMD_BLOCK_PATTERNS:
        if pat.search(command):
            return (
                "Blocked: bash may not touch OAuth/secret files or call Gmail/Google "
                "mail APIs. Use official Gmail tools for read/draft only; "
                "sending and deleting mail are not allowed."
            )
    return None


def scrub_environ(base: dict[str, str] | None = None) -> dict[str, str]:
    """Child env without obvious credential variables."""
    env = dict(base if base is not None else os.environ)
    for key in list(env):
        upper = key.upper()
        if any(s in upper for s in _ENV_BLOCK_SUBSTR):
            env.pop(key, None)
    return env


def drop_privs_preexec() -> None:
    """preexec_fn: drop root to nobody when enabled."""
    if os.environ.get("OMC_BASH_DROP_PRIVS", "1") == "0":
        return
    try:
        euid = os.geteuid()
    except AttributeError:
        return
    if euid != 0:
        return
    uid = int(os.environ.get("OMC_BASH_UID", "65534"))
    gid = int(os.environ.get("OMC_BASH_GID", str(uid)))
    os.setgid(gid)
    os.setuid(uid)


def bash_subprocess_kwargs() -> dict:
    """Extra kwargs for subprocess.run used by employee bash."""
    kwargs: dict = {
        "env": scrub_environ(),
    }
    if os.environ.get("OMC_BASH_DROP_PRIVS", "1") != "0":
        kwargs["preexec_fn"] = drop_privs_preexec
    return kwargs
