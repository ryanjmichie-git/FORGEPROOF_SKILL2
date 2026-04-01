"""Load ForgeProof config from .forgeproof.toml with sensible defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib  # Python 3.11+ stdlib


DEFAULTS: dict[str, Any] = {
    "paths": {
        "allowed": ["src/**/*", "lib/**/*", "app/**/*", "tests/**/*"],
        "denied": [".env", "**/*.key", "**/*.pem", ".github/**", ".gitlab-ci.yml"],
    },
    "evaluation": {
        "commands": [],
    },
    "gates": {
        "all_required_commands_pass": True,
        "requirements_coverage_min": 80,
    },
    "signing": {
        "ephemeral": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving base keys not in override."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load config from TOML file, merging with defaults."""
    if config_path and config_path.exists():
        with config_path.open("rb") as f:
            user_config = tomllib.load(f)
        return _deep_merge(DEFAULTS, user_config)
    return DEFAULTS.copy()
