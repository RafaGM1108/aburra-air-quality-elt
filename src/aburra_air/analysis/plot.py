"""Small matplotlib helpers shared by the analyses (headless, PNG only)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in CI
import matplotlib.pyplot as plt

COLOR = "#c2410c"


def barh(
    path: Path, labels: list[str], values: list[float], xlabel: str, title: str, note: str
) -> Path:
    """Save a horizontal bar chart, first label on top.

    Args:
        path: PNG file to write.
        labels: One label per bar.
        values: One value per bar.
        xlabel: X axis label.
        title: Chart title.
        note: Source and coverage line printed under the chart.

    Returns:
        ``path``.
    """
    figure, axis = plt.subplots(figsize=(8, max(3.0, 0.35 * len(labels) + 1)))
    axis.barh(labels[::-1], values[::-1], color=COLOR)
    axis.set_xlabel(xlabel)
    axis.set_title(title)
    figure.text(0.01, 0.01, note, fontsize=7)
    figure.tight_layout(rect=(0, 0.03, 1, 1))
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def lines(
    path: Path,
    x: list[float],
    series: dict[str, list[float | None]],
    xlabel: str,
    ylabel: str,
    title: str,
    note: str,
) -> Path:
    """Save a line chart with one line per series and a legend.

    Args:
        path: PNG file to write.
        x: Shared x values.
        series: Label to y values (``None`` for gaps).
        xlabel: X axis label.
        ylabel: Y axis label.
        title: Chart title.
        note: Source and coverage line printed under the chart.

    Returns:
        ``path``.
    """
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for label, values in series.items():
        axis.plot(x, [float("nan") if v is None else v for v in values], marker="o", label=label)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.legend()
    axis.grid(alpha=0.3)
    figure.text(0.01, 0.01, note, fontsize=7)
    figure.tight_layout(rect=(0, 0.03, 1, 1))
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path
