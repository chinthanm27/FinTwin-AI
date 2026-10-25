"""Plotly chart builders. Every chart uses the shared theme layout."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
from nicegui import ui

from app.styles.theme import CHART_SEQUENCE, COLORS, PLOTLY_CONFIG, plotly_layout
from app.utils.formatters import format_inr_compact, month_label


def _nice_step(span: float, target_ticks: int = 5) -> float:
    raw = span / max(1, target_ticks)
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for multiplier in (1, 2, 2.5, 5, 10):
        if raw <= multiplier * magnitude:
            return multiplier * magnitude
    return 10 * magnitude


def apply_inr_ticks(figure: dict[str, Any]) -> dict[str, Any]:
    """Label the primary y-axis in Indian units (₹50K, ₹2.5L, ₹1.2Cr) instead of k/M."""
    values: list[float] = []
    anchored_at_zero = False
    for trace in figure.get("data", []):
        if trace.get("yaxis") in (None, "y") and trace.get("type") in ("bar", "scatter"):
            values += [float(v) for v in trace.get("y", []) if isinstance(v, (int, float))]
            if trace.get("error_y"):
                values += [float(y) + float(e) for y, e in zip(trace.get("y", []), trace["error_y"].get("array", []))]
            anchored_at_zero |= trace.get("type") == "bar" or trace.get("fill") == "tozeroy"
    if not values:
        return figure
    if anchored_at_zero:
        low, high = min(0.0, min(values)), max(0.0, max(values))
    else:
        low, high = min(values), max(values)
    if high == low:
        return figure
    step = _nice_step(high - low)
    start = math.floor(low / step) * step
    ticks = []
    value = start
    while value <= high + step * 0.999:
        ticks.append(round(value, 2))
        value += step
    layout = figure.setdefault("layout", {})
    yaxis = dict(layout.get("yaxis", {}))
    yaxis.update({"tickmode": "array", "tickvals": ticks, "ticktext": [format_inr_compact(t) for t in ticks],
                  "tickprefix": "", "range": [ticks[0], ticks[-1]]})
    layout["yaxis"] = yaxis
    return figure


def render(figure: dict[str, Any], classes: str = "w-full") -> ui.plotly:
    """Render a figure dict with the shared config and Indian-unit axis labels."""
    return ui.plotly({**apply_inr_ticks(figure), "config": PLOTLY_CONFIG}).classes(classes)


def _labels(monthly: pd.DataFrame) -> list[str]:
    return [month_label(m) for m in monthly["month"]]


def income_vs_expenses(monthly: pd.DataFrame, height: int = 300) -> dict[str, Any]:
    x = _labels(monthly)
    return {
        "data": [
            {"type": "bar", "name": "Income", "x": x, "y": monthly["income"].round(0).tolist(),
             "marker": {"color": COLORS["mint"], "cornerradius": 6}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "bar", "name": "Expenses", "x": x, "y": monthly["expense"].round(0).tolist(),
             "marker": {"color": COLORS["coral"], "cornerradius": 6}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "bar", "name": "Investments", "x": x, "y": monthly["investment"].round(0).tolist(),
             "marker": {"color": COLORS["sky"], "cornerradius": 6}, "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, barmode="group", bargap=0.28, bargroupgap=0.08),
    }


def category_donut(categories: pd.DataFrame, height: int = 300) -> dict[str, Any]:
    top = categories.head(7)
    rest = categories.iloc[7:]["amount"].sum() if len(categories) > 7 else 0
    labels = top["category"].tolist() + (["Others"] if rest else [])
    values = top["amount"].round(0).tolist() + ([round(rest)] if rest else [])
    total = sum(values)
    return {
        "data": [{
            "type": "pie", "labels": labels, "values": values, "hole": 0.68, "sort": False,
            "marker": {"colors": CHART_SEQUENCE[: len(labels)], "line": {"color": COLORS["panel"], "width": 3}},
            "textinfo": "none", "hovertemplate": "%{label}<br>₹%{value:,.0f} · %{percent}<extra></extra>",
        }],
        "layout": plotly_layout(
            height, hovermode="closest", showlegend=True,
            legend={"orientation": "v", "x": 1.02, "y": 0.5, "font": {"color": COLORS["muted"], "size": 12}},
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            annotations=[{"text": f"<b>₹{total/1000:,.0f}K</b><br><span style='font-size:11px'>spent</span>",
                          "showarrow": False, "font": {"family": "Sora", "size": 18, "color": COLORS["text"]},
                          "x": 0.5, "y": 0.5, "xref": "paper", "yref": "paper"}],
        ),
    }


def savings_trend(monthly: pd.DataFrame, height: int = 280) -> dict[str, Any]:
    x = _labels(monthly)
    return {
        "data": [
            {"type": "scatter", "mode": "lines+markers", "name": "Savings", "x": x, "y": monthly["savings"].round(0).tolist(),
             "line": {"color": COLORS["mint"], "width": 3, "shape": "spline"}, "marker": {"size": 6},
             "fill": "tozeroy", "fillcolor": "rgba(62,230,176,0.08)", "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines", "name": "Savings rate", "x": x,
             "y": monthly["savings_rate"].round(1).tolist(), "yaxis": "y2",
             "line": {"color": COLORS["iris"], "width": 2, "dash": "dot"}, "hovertemplate": "%{y:.1f}%"},
        ],
        "layout": plotly_layout(
            height,
            yaxis2={"overlaying": "y", "side": "right", "ticksuffix": "%", "showgrid": False,
                    "tickfont": {"color": COLORS["muted"]}, "rangemode": "tozero"},
        ),
    }


def cash_flow(monthly: pd.DataFrame, height: int = 280) -> dict[str, Any]:
    x = _labels(monthly)
    net = monthly["net_cash_flow"].round(0).tolist()
    return {
        "data": [
            {"type": "bar", "name": "Net cash flow", "x": x, "y": net,
             "marker": {"color": [COLORS["mint"] if v >= 0 else COLORS["coral"] for v in net], "cornerradius": 5},
             "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines", "name": "Tracked cash", "x": x,
             "y": monthly["cumulative_balance"].round(0).tolist(),
             "line": {"color": COLORS["sky"], "width": 2.5, "shape": "spline"}, "fill": "tozeroy",
             "fillcolor": "rgba(76,194,255,0.07)", "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, bargap=0.4),
    }


def investment_trend(monthly: pd.DataFrame, height: int = 280) -> dict[str, Any]:
    x = _labels(monthly)
    return {
        "data": [
            {"type": "bar", "name": "Invested this month", "x": x, "y": monthly["investment"].round(0).tolist(),
             "marker": {"color": "rgba(76,194,255,0.35)", "cornerradius": 5}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines+markers", "name": "Total contributed", "x": x,
             "y": monthly["cumulative_investment"].round(0).tolist(),
             "line": {"color": COLORS["sky"], "width": 3, "shape": "spline"}, "marker": {"size": 5},
             "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, bargap=0.45),
    }


def twin_forecast(history: pd.DataFrame, months: list[str], values: list[float], low: list[float],
                  high: list[float], name: str, history_column: str, height: int = 320) -> dict[str, Any]:
    """The signature twin line: recorded history (mint) continuing as a projected band (iris)."""
    hx = _labels(history)
    hy = history[history_column].round(0).tolist()
    fx = [month_label(m) for m in months]
    bridge_x = hx[-1:] + fx
    bridge_y = hy[-1:] + values
    return {
        "data": [
            {"type": "scatter", "mode": "lines", "x": fx + fx[::-1], "y": high + low[::-1], "fill": "toself",
             "fillcolor": "rgba(139,124,255,0.14)", "line": {"width": 0}, "hoverinfo": "skip", "name": "Likely range"},
            {"type": "scatter", "mode": "lines+markers", "name": "Recorded", "x": hx, "y": hy,
             "line": {"color": COLORS["mint"], "width": 3, "shape": "spline"}, "marker": {"size": 5},
             "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines+markers", "name": f"Twin projection · {name}", "x": bridge_x, "y": bridge_y,
             "line": {"color": COLORS["iris"], "width": 3, "dash": "dash", "shape": "spline"},
             "marker": {"size": 6, "symbol": "circle-open"}, "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, xaxis={**plotly_layout()["xaxis"], "categoryorder": "array",
                                               "categoryarray": hx + fx}),
    }


def multi_forecast(forecast: Any, height: int = 320) -> dict[str, Any]:
    x = [month_label(m) for m in forecast.months]
    return {
        "data": [
            {"type": "bar", "name": "Income", "x": x, "y": forecast.income.values,
             "marker": {"color": "rgba(62,230,176,0.75)", "cornerradius": 5}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "bar", "name": "Expenses", "x": x, "y": forecast.expense.values,
             "marker": {"color": "rgba(255,107,129,0.75)", "cornerradius": 5}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines+markers", "name": "Savings", "x": x, "y": forecast.savings,
             "line": {"color": COLORS["iris"], "width": 3, "dash": "dash"}, "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, barmode="group", bargap=0.35),
    }


def wealth_chart(projection: Any, height: int = 340) -> dict[str, Any]:
    x = [f"Year {y}" for y in projection.years]
    data: list[dict[str, Any]] = [
        {"type": "scatter", "mode": "lines", "name": "Amount invested", "x": x, "y": projection.invested,
         "line": {"color": COLORS["faint"], "width": 2}, "fill": "tozeroy", "fillcolor": "rgba(140,152,181,0.10)",
         "hovertemplate": "₹%{y:,.0f}"},
    ]
    styles = [(COLORS["amber"], "dot"), (COLORS["iris"], "solid"), (COLORS["mint"], "dot")]
    for (label, values), (color, dash) in zip(projection.scenarios.items(), styles):
        data.append({"type": "scatter", "mode": "lines", "name": label, "x": x, "y": values,
                     "line": {"color": color, "width": 3 if dash == "solid" else 2, "dash": dash, "shape": "spline"},
                     "hovertemplate": "₹%{y:,.0f}"})
    data.append({"type": "scatter", "mode": "lines", "name": "Expected, in today's money", "x": x,
                 "y": projection.real_value, "line": {"color": COLORS["sky"], "width": 2, "dash": "dash"},
                 "hovertemplate": "₹%{y:,.0f}"})
    return {"data": data, "layout": plotly_layout(height)}


def scenario_chart(baseline: dict[str, Any], scenario: dict[str, Any], height: int = 300) -> dict[str, Any]:
    x = [f"M{p['month']}" for p in baseline["timeline"]]
    return {
        "data": [
            {"type": "scatter", "mode": "lines", "name": "Current path", "x": x,
             "y": [p["net_worth"] for p in baseline["timeline"]],
             "line": {"color": COLORS["mint"], "width": 3, "shape": "spline"}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "scatter", "mode": "lines", "name": "Your twin's scenario", "x": x,
             "y": [p["net_worth"] for p in scenario["timeline"]],
             "line": {"color": COLORS["iris"], "width": 3, "dash": "dash", "shape": "spline"},
             "fill": "tonexty", "fillcolor": "rgba(139,124,255,0.10)", "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, yaxis={**plotly_layout()["yaxis"], "title": None}),
    }


def spending_estimate(history: pd.DataFrame, prediction: Any, spent_so_far: float, height: int = 280) -> dict[str, Any]:
    recent = history.tail(6)
    x = _labels(recent)
    label = month_label(prediction.month) + " (est.)"
    return {
        "data": [
            {"type": "bar", "name": "Recorded spending", "x": x, "y": recent["expense"].round(0).tolist(),
             "marker": {"color": "rgba(255,107,129,0.55)", "cornerradius": 6}, "hovertemplate": "₹%{y:,.0f}"},
            {"type": "bar", "name": "Twin estimate", "x": [label], "y": [prediction.predicted],
             "marker": {"color": "rgba(139,124,255,0.55)", "line": {"color": COLORS["iris"], "width": 2}, "cornerradius": 6},
             "error_y": {"type": "data", "symmetric": False, "array": [prediction.high - prediction.predicted],
                         "arrayminus": [prediction.predicted - prediction.low], "color": COLORS["iris"], "thickness": 2},
             "hovertemplate": "Estimate ₹%{y:,.0f}"},
            {"type": "scatter", "mode": "markers", "name": "Spent so far", "x": [label], "y": [spent_so_far],
             "marker": {"color": COLORS["amber"], "size": 13, "symbol": "diamond"}, "hovertemplate": "₹%{y:,.0f}"},
        ],
        "layout": plotly_layout(height, bargap=0.35, hovermode="closest"),
    }


def health_gauge(score: int | None, color: str, height: int = 230) -> dict[str, Any]:
    return {
        "data": [{
            "type": "indicator", "mode": "gauge+number", "value": score or 0,
            "number": {"font": {"family": "Sora", "size": 46, "color": COLORS["text"]}, "suffix": ""},
            "gauge": {
                "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "rgba(0,0,0,0)",
                         "tickvals": [0, 30, 60, 80, 100], "tickfont": {"color": COLORS["faint"], "size": 11}},
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "rgba(255,255,255,0.04)", "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(255,107,129,0.10)"},
                    {"range": [30, 60], "color": "rgba(246,185,76,0.10)"},
                    {"range": [60, 80], "color": "rgba(139,124,255,0.10)"},
                    {"range": [80, 100], "color": "rgba(62,230,176,0.10)"},
                ],
            },
        }],
        "layout": plotly_layout(height, margin={"l": 36, "r": 36, "t": 16, "b": 0}),
    }
