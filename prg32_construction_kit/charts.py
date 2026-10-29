"""Charts of PRG32 evaluation data, as SVG and PDF from the same drawing (EVAL-01, docs/evaluate.md).

A chart is made only from an evaluation's dataset (evaluation.py): every measured value is
drawn as a point, so nothing is smoothed away or left out, and the bar and error bar of a case
are that case's mean and 95 % confidence interval. A case without measured values says "no
data" instead of drawing a zero. The same dataset always gives the same bytes (no clock, no
random numbers), so a chart can be made again from the downloaded dataset
(tools/evaluation_charts.py) and compared byte for byte.

Colours are the Okabe-Ito palette, which stays distinguishable with the common colour-vision
deficiencies, and each target also has its own point shape, so the chart can be read in
grey too. Text is in English, so a published chart is the same whatever the reader's interface
language. The SVG says what it shows (role="img", <title>, <desc>) and carries its provenance in
<metadata>; the PDF carries it in its document information.
"""

from __future__ import annotations

import json
import math
from typing import Any

OKABE_ITO = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9")
SHAPES = ("circle", "square", "triangle", "diamond", "circle", "square")
WIDTH, HEIGHT = 760, 460
LEFT, RIGHT, TOP, BOTTOM = 80, 20, 64, 120       # room for the axes, the legend and the caption


class Canvas:
    """The few drawing words a chart needs, kept as a list, written out as SVG or PDF."""

    def __init__(self, width: int, height: int):
        self.width, self.height, self.items = width, height, []

    def rect(self, x, y, w, h, fill, stroke=None):
        self.items.append(("rect", x, y, w, h, fill, stroke))

    def line(self, x1, y1, x2, y2, stroke, width=1.0, dash=False):
        self.items.append(("line", x1, y1, x2, y2, stroke, width, dash))

    def mark(self, shape, x, y, size, fill, stroke="#000000"):
        self.items.append(("mark", shape, x, y, size, fill, stroke))

    def text(self, x, y, value, size=11, anchor="start", weight="normal", rotate=False, fill="#000000"):
        self.items.append(("text", x, y, str(value), size, anchor, weight, rotate, fill))

    # --- SVG -----------------------------------------------------------------------------

    def svg(self, title: str, description: str, provenance: dict[str, Any]) -> bytes:
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
               f'width="{self.width}" height="{self.height}" role="img" aria-labelledby="chart-title chart-desc" '
               'font-family="Helvetica, Arial, sans-serif">',
               f'<title id="chart-title">{_xml(title)}</title>', f'<desc id="chart-desc">{_xml(description)}</desc>',
               f'<metadata>{_xml(json.dumps(provenance, sort_keys=True, separators=(",", ":")))}</metadata>',
               f'<rect x="0" y="0" width="{self.width}" height="{self.height}" fill="#ffffff"/>']
        for item in self.items:
            kind = item[0]
            if kind == "rect":
                _, x, y, w, h, fill, stroke = item
                out.append(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" fill="{fill}"'
                           + (f' stroke="{stroke}"' if stroke else "") + "/>")
            elif kind == "line":
                _, x1, y1, x2, y2, stroke, width, dash = item
                out.append(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" stroke="{stroke}" '
                           f'stroke-width="{_n(width)}"' + (' stroke-dasharray="3 3"' if dash else "") + "/>")
            elif kind == "mark":
                _, shape, x, y, size, fill, stroke = item
                out.append(_svg_mark(shape, x, y, size, fill, stroke))
            else:
                _, x, y, value, size, anchor, weight, rotate, fill = item
                turn = f' transform="rotate(-90 {_n(x)} {_n(y)})"' if rotate else ""
                out.append(f'<text x="{_n(x)}" y="{_n(y)}" font-size="{size}" text-anchor="{anchor}" '
                           f'font-weight="{weight}" fill="{fill}"{turn}>{_xml(value)}</text>')
        out.append("</svg>")
        return ("\n".join(out) + "\n").encode("utf-8")

    # --- PDF (one page, vector, the PDF core font Helvetica: nothing embedded) --------------

    def pdf(self, title: str, description: str, provenance: dict[str, Any]) -> bytes:
        ops = ["1 1 1 rg", f"0 0 {self.width} {self.height} re f"]
        for item in self.items:
            kind = item[0]
            if kind == "rect":
                _, x, y, w, h, fill, stroke = item
                ops.append(f"{_rgb(fill)} rg {_n(x)} {_n(self.height - y - h)} {_n(w)} {_n(h)} re f")
                if stroke:
                    ops.append(f"{_rgb(stroke)} RG 0.8 w {_n(x)} {_n(self.height - y - h)} {_n(w)} {_n(h)} re S")
            elif kind == "line":
                _, x1, y1, x2, y2, stroke, width, dash = item
                ops.append(("[3 3] 0 d " if dash else "[] 0 d ") + f"{_rgb(stroke)} RG {_n(width)} w "
                           f"{_n(x1)} {_n(self.height - y1)} m {_n(x2)} {_n(self.height - y2)} l S")
            elif kind == "mark":
                _, shape, x, y, size, fill, stroke = item
                ops.append("[] 0 d " + _pdf_mark(shape, x, self.height - y, size, fill, stroke))
            else:
                _, x, y, value, size, anchor, weight, rotate, fill = item
                font = "/F2" if weight == "bold" else "/F1"
                width = _text_width(value, size)
                shift = {"start": 0, "middle": width / 2, "end": width}[anchor]
                if rotate:
                    ops.append(f"BT {_rgb(fill)} rg {font} {size} Tf 0 1 -1 0 {_n(x)} {_n(self.height - y - shift)} Tm "
                               f"({_pdf_text(value)}) Tj ET")
                else:
                    ops.append(f"BT {_rgb(fill)} rg {font} {size} Tf {_n(x - shift)} {_n(self.height - y)} Td "
                               f"({_pdf_text(value)}) Tj ET")
        content = "\n".join(ops).encode("latin-1", "replace")
        info = (f"<< /Title ({_pdf_text(title)}) /Subject ({_pdf_text(description)}) "
                f"/Keywords ({_pdf_text(json.dumps(provenance, sort_keys=True, separators=(',', ':')))}) "
                "/Producer (PRG32 Construction Kit charts.py) >>")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width} {self.height}] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>".encode(),
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            info.encode("latin-1", "replace"),
        ]
        out, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
        out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 7 0 R >>\nstartxref\n{xref}\n%%EOF\n").encode()
        return bytes(out)


def _n(value: float) -> str:
    """A number for SVG/PDF: at most two decimals, always a dot (locale-independent)."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _rgb(colour: str) -> str:
    return " ".join(_n(int(colour[index:index + 2], 16) / 255) for index in (1, 3, 5))


def _pdf_text(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_width(text: str, size: float) -> float:
    return len(text) * size * 0.52            # Helvetica's average advance; enough to centre a label


def _svg_mark(shape, x, y, size, fill, stroke) -> str:
    r = size / 2
    if shape == "square":
        return f'<rect x="{_n(x - r)}" y="{_n(y - r)}" width="{_n(size)}" height="{_n(size)}" fill="{fill}" stroke="{stroke}"/>'
    if shape in ("triangle", "diamond"):
        points = _polygon(shape, x, y, r)
        return f'<polygon points="{" ".join(f"{_n(px)},{_n(py)}" for px, py in points)}" fill="{fill}" stroke="{stroke}"/>'
    return f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r)}" fill="{fill}" stroke="{stroke}"/>'


def _polygon(shape, x, y, r):
    if shape == "triangle":
        return [(x, y - r), (x + r, y + r), (x - r, y + r)]
    return [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]


def _pdf_mark(shape, x, y, size, fill, stroke) -> str:
    """``y`` is already in PDF space (from the bottom)."""
    r = size / 2
    paint = f"{_rgb(fill)} rg {_rgb(stroke)} RG 0.6 w"
    if shape == "square":
        return f"{paint} {_n(x - r)} {_n(y - r)} {_n(size)} {_n(size)} re B"
    if shape in ("triangle", "diamond"):
        points = [(px, 2 * y - py) for px, py in _polygon(shape, x, y, r)]
        path = f"{_n(points[0][0])} {_n(points[0][1])} m " + " ".join(f"{_n(px)} {_n(py)} l" for px, py in points[1:])
        return f"{paint} {path} h B"
    k = 0.5523 * r                                     # four Bezier quarters make a circle
    return (f"{paint} {_n(x + r)} {_n(y)} m {_n(x + r)} {_n(y + k)} {_n(x + k)} {_n(y + r)} {_n(x)} {_n(y + r)} c "
            f"{_n(x - k)} {_n(y + r)} {_n(x - r)} {_n(y + k)} {_n(x - r)} {_n(y)} c "
            f"{_n(x - r)} {_n(y - k)} {_n(x - k)} {_n(y - r)} {_n(x)} {_n(y - r)} c "
            f"{_n(x + k)} {_n(y - r)} {_n(x + r)} {_n(y - k)} {_n(x + r)} {_n(y)} c B")


def nice_top(value: float) -> tuple[float, float]:
    """An axis top at or above ``value`` and its tick step: 1, 2 or 5 times a power of ten."""
    if value <= 0:
        return 1.0, 0.2
    power = 10 ** math.floor(math.log10(value))
    for step in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10):
        if value / (step * power) <= 6:
            tick = step * power
            return math.ceil(value / tick) * tick, tick
    return value, value / 5


def bar_chart(series: list[dict[str, Any]], cases: list[str], metric: dict[str, str], title: str,
              caption: list[str], provenance: dict[str, Any]) -> Canvas:
    """Bars of each series' per-case mean with its 95 % interval, and every measured value as a point.

    ``series``: [{"name", "evidence", "cases": {case: {"values": [...], "mean", "ci95_low", "ci95_high"}}}]."""
    canvas = Canvas(WIDTH, HEIGHT)
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    highest = max([value for item in series for case in item["cases"].values()
                   for value in case["values"] + [case.get("ci95_high") or 0]] or [0])
    top, tick = nice_top(highest * 1.05)
    canvas.text(LEFT, 24, title, size=15, weight="bold")
    canvas.text(LEFT, 44, f"{metric['label']} ({metric['unit']}); bar: mean, line: 95% CI, dots: each measured run",
                size=11, fill="#333333")
    value = 0.0
    while value <= top + tick / 1000:
        y = TOP + plot_h - value / top * plot_h
        canvas.line(LEFT, y, LEFT + plot_w, y, "#dddddd", 1, dash=value > 0)
        canvas.text(LEFT - 6, y + 4, _number(value), size=10, anchor="end")
        value += tick
    canvas.line(LEFT, TOP, LEFT, TOP + plot_h, "#000000", 1)
    canvas.line(LEFT, TOP + plot_h, LEFT + plot_w, TOP + plot_h, "#000000", 1)
    canvas.text(18, TOP + plot_h / 2, f"{metric['label']} ({metric['unit']})", size=11, anchor="middle", rotate=True)
    group = plot_w / max(1, len(cases))
    width = min(48.0, group * 0.8 / max(1, len(series)))
    for index, case in enumerate(cases):
        centre = LEFT + group * (index + 0.5)
        canvas.text(centre, TOP + plot_h + 18, case, size=11, anchor="middle")
        for number, item in enumerate(series):
            colour, shape = OKABE_ITO[number % len(OKABE_ITO)], SHAPES[number % len(SHAPES)]
            x = centre + (number - (len(series) - 1) / 2) * width
            data = item["cases"].get(case)
            if not data or not data["values"]:
                canvas.text(x, TOP + plot_h - 6, "no data", size=9, anchor="middle", fill="#555555")
                continue
            height = data["mean"] / top * plot_h
            canvas.rect(x - width * 0.4, TOP + plot_h - height, width * 0.8, height, _lighter(colour), colour)
            if data.get("ci95_low") is not None and data.get("ci95_high") is not None:
                low, high = (TOP + plot_h - data[key] / top * plot_h for key in ("ci95_low", "ci95_high"))
                canvas.line(x, low, x, high, "#000000", 1.4)
                canvas.line(x - 5, low, x + 5, low, "#000000", 1.4)
                canvas.line(x - 5, high, x + 5, high, "#000000", 1.4)
            for position, measured in enumerate(data["values"]):
                spread = (position - (len(data["values"]) - 1) / 2) * min(3.0, width * 0.3 / max(1, len(data["values"])))
                canvas.mark(shape, x + spread, TOP + plot_h - measured / top * plot_h, 6, colour)
    legend_y = TOP + plot_h + 40
    for number, item in enumerate(series):
        colour, shape = OKABE_ITO[number % len(OKABE_ITO)], SHAPES[number % len(SHAPES)]
        x = LEFT + (number % 3) * 220
        y = legend_y + (number // 3) * 16
        canvas.mark(shape, x + 5, y - 4, 8, colour)
        canvas.text(x + 14, y, f"{item['name']} ({item['evidence']})", size=10)
    for line, text in enumerate(caption):         # the last line 10 px above the bottom edge
        canvas.text(LEFT, HEIGHT - 10 - 13 * (len(caption) - 1 - line), text, size=9, fill="#333333")
    return canvas


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _lighter(colour: str) -> str:
    """The colour mixed halfway with white: the bar, under its darker outline and points."""
    parts = [int(colour[index:index + 2], 16) for index in (1, 3, 5)]
    return "#" + "".join(f"{(part + 255) // 2:02x}" for part in parts)
