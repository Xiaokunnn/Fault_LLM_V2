from __future__ import annotations

from scripts.run_rp2_v6_retrieval_latency import _percentile, _rotated


def test_v6_latency_rotation_balances_first_position() -> None:
    methods = [{"id": value} for value in "ABCDE"]
    first = [_rotated(methods, offset)[0]["id"] for offset in range(5)]
    assert first == list("ABCDE")


def test_v6_latency_percentile_uses_linear_interpolation() -> None:
    assert _percentile([1.0, 2.0, 3.0], 0.5) == 2.0
    assert _percentile([0.0, 10.0], 0.95) == 9.5
    assert _percentile([], 0.95) == 0.0
