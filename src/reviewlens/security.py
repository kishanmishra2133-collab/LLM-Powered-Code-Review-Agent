"""Security utilities: PR URL validation and secret redaction."""

import re

from reviewlens.models import PRRef

# GitHub PR URL pattern: https://github.com/{owner}/{repo}/pull/{number}
_PR_URL_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)/pull/(?P<number>\d+)/?$"
)

# Common secret patterns for redaction
_SECRET_PATTERNS = [
    # GitHub tokens (personal access tokens, oauth, fine-grained)
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"gho_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{82}"),
    # Google API keys
    re.compile(r"AIza[0-9A-Za-z\-_]{30,40}"),
    # AWS access key ID
    re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
    # Generic bearer tokens
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.=:_+/]{20,}"),
    # PEM Private keys
    re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"),
]


def parse_pr_url(url: str, head_sha: str = "") -> PRRef:
    """Parse and validate a GitHub pull request URL strictly.

    Raises ValueError if URL does not match the expected GitHub PR format.
    """
    cleaned_url = url.strip()
    match = _PR_URL_PATTERN.match(cleaned_url)
    if not match:
        raise ValueError(
            f"Invalid GitHub PR URL: '{url}'. Expected format: https://github.com/owner/repo/pull/number"
        )

    owner = match.group("owner")
    repo = match.group("repo")
    number = int(match.group("number"))

    return PRRef(owner=owner, repo=repo, number=number, head_sha=head_sha)


def redact_secrets(text: str) -> str:
    """Redact known API keys, tokens, and private keys from text."""
    if not text:
        return text

    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted
