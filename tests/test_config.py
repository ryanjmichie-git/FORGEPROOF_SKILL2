"""Tests for lib/config.py — config loading and merging."""
from pathlib import Path

import pytest

from config import DEFAULTS, load_config


def test_load_config_no_file_returns_defaults(tmp_path):
    cfg = load_config(None)
    assert cfg["paths"]["allowed"] == DEFAULTS["paths"]["allowed"]
    assert cfg["signing"]["ephemeral"] is True


def test_load_config_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.toml")
    assert cfg == DEFAULTS.copy()


def test_load_config_merges_user_values(tmp_path):
    toml = tmp_path / ".forgeproof.toml"
    toml.write_text('[signing]\nephemeral = false\n', encoding="utf-8")
    cfg = load_config(toml)
    assert cfg["signing"]["ephemeral"] is False
    # Unrelated keys should be preserved from defaults.
    assert cfg["paths"]["allowed"] == DEFAULTS["paths"]["allowed"]


def test_load_config_user_paths_override_defaults(tmp_path):
    toml = tmp_path / ".forgeproof.toml"
    toml.write_text('[paths]\nallowed = ["custom/**/*"]\n', encoding="utf-8")
    cfg = load_config(toml)
    assert cfg["paths"]["allowed"] == ["custom/**/*"]


def test_load_config_deep_merge_preserves_sibling_keys(tmp_path):
    toml = tmp_path / ".forgeproof.toml"
    toml.write_text('[gates]\nrequirements_coverage_min = 100\n', encoding="utf-8")
    cfg = load_config(toml)
    assert cfg["gates"]["requirements_coverage_min"] == 100
    assert cfg["gates"]["all_required_commands_pass"] is True
