"""
engram/redact.py

Scrubs sensitive values from commands and output before they are stored.
Patterns cover the most common cases: API keys, tokens, passwords in env
exports, Authorization headers, and connection strings.

Users can add their own patterns via ~/.engram/redact_patterns.txt —
one Python regex per line. Lines starting with # are ignored.
"""

import re
import os
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Built-in patterns
# Each entry is (label, compiled_regex, replacement)
# ---------------------------------------------------------------------------
_BUILTIN_PATTERNS: List[Tuple[str, re.Pattern, str]] = []


def _add(label: str, pattern: str, replacement: str = "[REDACTED]") -> None:
    _BUILTIN_PATTERNS.append((label, re.compile(pattern, re.IGNORECASE), replacement))


# AWS
_add("aws_access_key",     r"(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])")
_add("aws_secret_key",     r"aws.{0,20}secret.{0,20}['\"]?([A-Za-z0-9/+=]{40})")

# Generic API keys / tokens after key-like words
_add("api_key_header",     r"(api[-_]?key|apikey|access[-_]?token|secret[-_]?key)\s*[=:]\s*['\"]?([A-Za-z0-9\-_.~+/]{16,})")
_add("bearer_token",       r"bearer\s+([A-Za-z0-9\-_.~+/=]{16,})")
_add("authorization",      r"(Authorization:\s*)(Basic|Bearer|Token)\s+([A-Za-z0-9+/=\-_.]{16,})")

# Passwords / secrets / tokens / keys in export statements
_add("export_password",    r"(export\s+\w*pass\w*\s*=\s*)['\"]?([^\s'\"]+)")
_add("export_secret",      r"(export\s+\w*secret\w*\s*=\s*)['\"]?([^\s'\"]+)")
_add("export_token",       r"(export\s+\w*token\w*\s*=\s*)['\"]?([^\s'\"]+)")
_add("export_key",         r"(export\s+\w*key\w*\s*=\s*)['\"]?([^\s'\"]+)")

# curl -u user:pass
_add("curl_user_pass",     r"(-u\s+)([^\s:]+:[^\s]+)")
# curl -H "X-Api-Key: ..."
_add("curl_header_secret", r"(-H\s+['\"]?[^'\"]*(?:key|token|secret|auth)[^'\"]*:\s*)([^'\">|\s]{8,})")

# Database connection strings:  protocol://user:password@host
_add("conn_string",        r"((?:postgres|postgresql|mysql|mongodb)://[^:]+:)([^@\s]+)(@)")

# PEM private keys
_add("pem_key",
     r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
     "[PRIVATE KEY REDACTED]")

# Well-known token formats
_add("github_token",       r"ghp_[A-Za-z0-9]{36,}")
_add("gitlab_token",       r"glpat-[A-Za-z0-9\-_]{20,}")
_add("anthropic_key",      r"sk-ant-[A-Za-z0-9\-_]{32,}")
_add("openai_key",         r"sk-[A-Za-z0-9]{32,}")


# ---------------------------------------------------------------------------
# User-defined patterns (~/.engram/redact_patterns.txt)
# ---------------------------------------------------------------------------

def _load_user_patterns() -> List[Tuple[str, re.Pattern, str]]:
    engram_dir = Path(os.environ.get("ENGRAM_DIR", Path.home() / ".engram"))
    path = engram_dir / "redact_patterns.txt"
    if not path.exists():
        return []
    patterns: List[Tuple[str, re.Pattern, str]] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append((f"user_pattern_{i}", re.compile(line), "[REDACTED]"))
        except re.error:
            pass  # silently skip invalid regexes
    return patterns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def redact(text: str) -> str:
    """
    Apply all built-in and user-defined redaction patterns to `text`.
    Returns the scrubbed string. Safe to call with empty string.
    """
    if not text:
        return text
    all_patterns = _BUILTIN_PATTERNS + _load_user_patterns()
    for _label, pattern, replacement in all_patterns:
        text = pattern.sub(replacement, text)
    return text


def is_sensitive_command(command: str) -> bool:
    """
    Return True if this command should be skipped entirely (not stored at all).
    Covers interactive password-setting and key-generation commands.
    """
    skip_prefixes = (
        "sudo passwd",
        "passwd ",
        "passwd\n",
        "chpasswd",
        "openssl genrsa",
        "openssl req",
        "gpg --gen-key",
        "gpg --import",
        "ssh-keygen",
    )
    cmd_lower = command.strip().lower()
    return any(cmd_lower.startswith(p) for p in skip_prefixes)
