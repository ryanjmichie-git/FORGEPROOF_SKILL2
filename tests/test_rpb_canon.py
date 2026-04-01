"""Tests for rpb.canon — canonical JSON serialisation."""
import pytest
from rpb.canon import dumps_canonical, loads_json


def test_dumps_canonical_sorts_keys():
    result = dumps_canonical({"z": 1, "a": 2, "m": 3})
    assert result == b'{"a":2,"m":3,"z":1}'


def test_dumps_canonical_no_whitespace():
    result = dumps_canonical({"key": "value", "n": 42})
    assert b" " not in result
    assert b"\n" not in result


def test_dumps_canonical_nested_keys_sorted():
    result = dumps_canonical({"b": {"z": 1, "a": 2}, "a": 0})
    assert result == b'{"a":0,"b":{"a":2,"z":1}}'


def test_dumps_canonical_utf8_encoding():
    result = dumps_canonical({"emoji": "\u2603"})
    assert isinstance(result, bytes)
    assert "\u2603".encode("utf-8") in result


def test_dumps_canonical_rejects_nan():
    with pytest.raises((ValueError, TypeError)):
        dumps_canonical(float("nan"))


def test_dumps_canonical_array_order_preserved():
    result = dumps_canonical([3, 1, 2])
    assert result == b"[3,1,2]"


def test_loads_json_parses_bytes():
    result = loads_json(b'{"x": 1}')
    assert result == {"x": 1}


def test_loads_json_roundtrip():
    obj = {"z": [1, 2], "a": {"nested": True}}
    assert loads_json(dumps_canonical(obj)) == obj
