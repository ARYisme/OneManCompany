"""Tests for employee bash / path guards (Gmail bypass hardening)."""

from pathlib import Path

import pytest

from onemancompany.core.bash_guard import (
    check_bash_command,
    is_sensitive_path,
    scrub_environ,
)


@pytest.mark.parametrize("cmd", [
    "cat /workspace/.onemancompany/company/assets/.oauth_cache/gmail_tokens.json",
    "curl https://gmail.googleapis.com/gmail/v1/users/me/drafts",
    "python gmail_delete.py",
    "wget https://www.googleapis.com/gmail/v1/users/me/messages/send",
    "echo /run/secrets/google_oauth_client.json",
])
def test_blocks_secret_and_gmail_commands(cmd):
    assert check_bash_command(cmd) is not None


@pytest.mark.parametrize("cmd", [
    "ls /tmp",
    "python -m pytest tests/unit/test_bash_guard.py",
    "curl https://example.com",
    "echo hello",
])
def test_allows_normal_commands(cmd):
    assert check_bash_command(cmd) is None


def test_sensitive_path_oauth_name():
    assert is_sensitive_path("/x/company/assets/.oauth_cache/gmail_tokens.json")
    assert is_sensitive_path(Path("/run/secrets/google_oauth_client.json"))
    assert not is_sensitive_path("/workspace/.onemancompany/company/shared_prompts/tool_usage.md")


def test_scrub_environ_removes_secrets():
    cleaned = scrub_environ({
        "PATH": "/usr/bin",
        "CUSTOM_API_KEY": "x",
        "FOUNDRY_LITELLM_API_KEY": "y",
        "HOME": "/root",
    })
    assert cleaned["PATH"] == "/usr/bin"
    assert cleaned["HOME"] == "/root"
    assert "CUSTOM_API_KEY" not in cleaned
    assert "FOUNDRY_LITELLM_API_KEY" not in cleaned
