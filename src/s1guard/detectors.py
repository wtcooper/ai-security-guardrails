"""Deterministic detectors for signals a classifier reads poorly: exact secret formats,
invisible characters, markdown exfiltration URLs, injected shell/SQL syntax and credential file
paths. Each returns 1.0 (hit) or 0.0."""

import re

_SECRET_PATTERNS = [
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),                                  # AWS access key id
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY( BLOCK)?-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),                               # GitHub token
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),                             # Slack token
    re.compile(r"\bsk-(proj-|ant-)?[A-Za-z0-9_-]{20,}\b"),                       # OpenAI / Anthropic style key
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),                                    # Google API key
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT
    re.compile(r"(?i)\b(aws_secret_access_key|password|passwd|secret|api[_-]?key|access[_-]?token)\b"
               r"\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
]

# Unicode tag block (ASCII smuggling), bidi overrides/isolates.
_INVISIBLE = re.compile("[\U000E0000-\U000E007F‪-‮⁦-⁩]")
# Zero-width chars are common in normal text, so only a run of them counts.
_ZERO_WIDTH_RUN = re.compile("[​-‍⁠﻿]{3,}")

# Markdown image/link whose URL carries a query string -- the classic render-time exfil channel.
_MD_EXFIL = re.compile(r"!\[[^\]]*\]\(\s*https?://[^)\s]+\?[^)\s]*=[^)\s]+\)")

# Shell chaining into another program, command substitution, pipe-to-shell, stacked/tautology SQL.
_CMD_INJECTION = [
    re.compile(r"(;|&&|\|\|?)\s*(curl|wget|nc|ncat|bash|sh|zsh|python3?|perl|powershell|rm|chmod)\b"),
    re.compile(r"\$\([^)]+\)|`[^`]+`"),
    re.compile(r"(?i);\s*(drop|delete|truncate|alter|insert|update|grant)\s"),
    re.compile(r"(?i)\bunion\s+(all\s+)?select\b|'\s*or\s+'?1'?\s*=\s*'?1"),
]

_SENSITIVE_PATH = re.compile(
    r"(/etc/(shadow|passwd|sudoers)|\.ssh/|id_(rsa|ed25519|ecdsa)\b|\.aws/credentials|\.kube/config"
    r"|\.git-credentials|\.netrc|\.npmrc|(^|[/\"'\s])\.env\b)")


def secret_leak(text: str) -> float:
    return 1.0 if any(p.search(text) for p in _SECRET_PATTERNS) else 0.0


def invisible_text(text: str) -> float:
    return 1.0 if _INVISIBLE.search(text) or _ZERO_WIDTH_RUN.search(text) else 0.0


def markdown_exfil(text: str) -> float:
    return 1.0 if _MD_EXFIL.search(text) else 0.0


def command_injection(text: str) -> float:
    return 1.0 if any(p.search(text) for p in _CMD_INJECTION) else 0.0


def sensitive_file_access(text: str) -> float:
    return 1.0 if _SENSITIVE_PATH.search(text) else 0.0


DETECTORS = {
    "secret_leak": secret_leak,
    "invisible_text": invisible_text,
    "markdown_exfil": markdown_exfil,
    "command_injection": command_injection,
    "sensitive_file_access": sensitive_file_access,
}
