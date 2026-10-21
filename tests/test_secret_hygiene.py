"""T-SEC-01: Secret scan passes on the working tree; .env is ignored by git (SEC-026, SEC-027)."""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        "venv",
    }
)


def test_gitignore_covers_sensitive_files():
    """Verify .gitignore blocks .env, database files, and keys."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist in repo root"

    content = gitignore_path.read_text(encoding="utf-8")
    lines = [
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    ]

    assert ".env" in lines, ".env must be ignored"
    assert ".env.*" in lines, ".env.* must be ignored"
    assert "!.env.example" in lines, "!.env.example must be preserved"
    assert "*.pem" in lines or "*.key" in lines, "Key files must be ignored"
    assert any("sqlite" in line or "*.db" in line for line in lines), "Databases must be ignored"


def test_env_file_not_committed():
    """.env file must never be tracked or committed in git repository."""
    import subprocess
    result = subprocess.run(
        ["git", "ls-files", ".env"],  # noqa: S603, S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "", ".env file must not be tracked in git"


def test_env_example_contains_placeholders_only():
    """.env.example must contain only placeholders (REPLACE_ME or blank), never real values."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist"

    lines = env_example.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("#")[0].strip().split("=", 1)
        if len(parts) == 2:
            key, val = parts[0].strip(), parts[1].strip()
            allowed_defaults = {"Asia/Kolkata", "false", "true", ""}
            assert val == "REPLACE_ME" or val in allowed_defaults, (
                f"Setting {key} has unexpected non-placeholder value '{val}' in .env.example"
            )


def test_working_tree_secret_scan():
    """Scan all project files for accidental leaks of tokens, keys, or credentials."""
    suspicious_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
        re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq API key format
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API key format
        re.compile(r"\b\d{9,10}:[A-Za-z0-9_-]{35}\b"),  # Telegram bot token format
    ]

    scanned_files = 0
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_path = Path(root) / file
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            scanned_files += 1
            rel_path = file_path.relative_to(REPO_ROOT)
            for pattern in suspicious_patterns:
                match = pattern.search(content)
                assert match is None, f"Secret pattern '{pattern.pattern}' found in {rel_path}"

    assert scanned_files > 0, "Working tree scan must inspect repository files"
