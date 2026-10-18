from pathlib import Path

from aburra_air.analysis.plot import barh, lines


def test_barh_writes_a_png(tmp_path: Path) -> None:
    path = barh(tmp_path / "bars.png", ["a", "b"], [1.0, 2.0], "x", "title", "note")
    assert path.read_bytes().startswith(b"\x89PNG")


def test_lines_writes_a_png_with_gaps(tmp_path: Path) -> None:
    path = lines(tmp_path / "lines.png", [0.0, 1.0], {"s": [1.0, None]}, "x", "y", "t", "n")
    assert path.read_bytes().startswith(b"\x89PNG")
