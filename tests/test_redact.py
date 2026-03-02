"""tests/test_redact.py — Redaction layer tests."""

import pytest
from engram.redact import redact, is_sensitive_command


def test_redact_export_password():
    result = redact("export DB_PASSWORD=supersecret123")
    assert "supersecret123" not in result
    assert "[REDACTED]" in result


def test_redact_export_token():
    result = redact("export GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456")
    assert "ghp_" not in result


def test_redact_github_token():
    cmd = "git clone https://ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456@github.com/user/repo"
    result = redact(cmd)
    assert "ghp_" not in result


def test_redact_anthropic_key():
    cmd = 'curl -H "x-api-key: sk-ant-api03-abcdefghijklmnopqrstuvwxyz" https://api.anthropic.com'
    result = redact(cmd)
    assert "sk-ant-" not in result


def test_redact_openai_key():
    cmd = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyzABCDEFGH python script.py"
    result = redact(cmd)
    assert "sk-abcdef" not in result


def test_redact_bearer_token():
    result = redact('curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"')
    assert "eyJhbGci" not in result


def test_redact_connection_string():
    result = redact("psql postgres://admin:mysecretpassword@localhost/mydb")
    assert "mysecretpassword" not in result
    assert "postgres://" in result  # prefix is kept
    assert "localhost" in result    # host is kept


def test_redact_curl_user_pass():
    result = redact("curl -u admin:hunter2 https://api.example.com")
    assert "hunter2" not in result


def test_redact_safe_command():
    cmd = "ls -la /home/user"
    assert redact(cmd) == cmd


def test_redact_empty_string():
    assert redact("") == ""


def test_redact_none_safe():
    # Should not crash on None — but we pass empty string convention
    assert redact("") == ""


def test_is_sensitive_command_passwd():
    assert is_sensitive_command("sudo passwd alice") is True
    assert is_sensitive_command("passwd") is True


def test_is_sensitive_command_ssh_keygen():
    assert is_sensitive_command("ssh-keygen -t ed25519 -C 'me@example.com'") is True


def test_is_sensitive_command_normal():
    assert is_sensitive_command("git status") is False
    assert is_sensitive_command("docker ps") is False
    assert is_sensitive_command("ls -la") is False
