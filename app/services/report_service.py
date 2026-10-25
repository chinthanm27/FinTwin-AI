"""
Financial report generation and export.

A report bundles summary metrics, categories, budget performance, the
health indicator, potential anomalies, the forecast and recommendations.
It can be exported as a self-contained HTML file (print to PDF from any
browser) or as CSV of the underlying transactions.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any

from app.ai.cashflow_forecast import forecast_cashflow
from app.ai.financial_twin import FinancialTwin
from app.database import insight_repository
from app.services import analytics_service, budget_service, fraud_service
from app.services.analytics_service import PERIODS
from app.services.health_service import weakest_factors
from app.services.transaction_service import transactions_dataframe
from app.utils.dates import utcnow
from app.utils.formatters import format_date, format_inr, format_percent


@dataclass
class FinancialReport:
    user_name: str
    period: str
    period_label: str
    generated_at: str
    summary: dict[str, float]
    monthly: list[dict[str, Any]]
    top_categories: list[dict[str, Any]]
    budgets: list[dict[str, Any]]
    health: dict[str, Any]
    anomalies: list[dict[str, Any]]
    forecast: dict[str, Any] | None
    recommendations: list[str] = field(default_factory=list)
    has_data: bool = True


def build_report(user_id: str, user_name: str, period: str = "3M") -> FinancialReport:
    df = transactions_dataframe(user_id)
    profile = insight_repository.get_profile(user_id)
    period_df = analytics_service.filter_period(df, period)
    summary = analytics_service.compute_summary(period_df)
    monthly = analytics_service.monthly_overview(period_df) if not period_df.empty else None
    categories = analytics_service.category_breakdown(period_df)
    statuses = budget_service.budget_status(user_id, df)
    twin = FinancialTwin.from_dataframe(df, profile)
    health = twin.health
    alerts = [a for a in fraud_service.get_alerts(user_id) if a.get("status") != "dismissed"][:10]
    forecast = forecast_cashflow(df, 3) if not df.empty else None

    recommendations: list[str] = []
    if health and health.available:
        recommendations += [f"{f.name}: {f.tip}" for f in weakest_factors(health, 3)]
    for insight in twin.key_insights(open_alerts=len(alerts), budget_alerts=budget_service.budget_alerts(statuses)):
        if insight["tone"] in {"warning", "negative"}:
            recommendations.append(f"{insight['title']}: {insight['text']}")
    if not recommendations and not df.empty:
        recommendations.append("Your finances look steady. Keep investing consistently and review goals quarterly.")

    report = FinancialReport(
        user_name=user_name,
        period=period,
        period_label=PERIODS.get(period, period),
        generated_at=utcnow().strftime("%d %b %Y, %H:%M UTC"),
        summary=summary.to_dict(),
        monthly=monthly.to_dict("records") if monthly is not None else [],
        top_categories=categories.head(8).to_dict("records"),
        budgets=[{"category": s.category, "budget": s.budget, "spent": s.spent, "remaining": s.remaining,
                  "percent": round(s.percent_used, 1), "status": s.status} for s in statuses],
        health={
            "score": health.score if health else None,
            "band": health.band if health else "Not enough data",
            "factors": [{"name": f.name, "score": f.score, "value": f.value_text} for f in (health.factors if health else [])],
            "notes": health.notes if health else [],
        },
        anomalies=[{"date": a.get("date"), "description": a.get("description"), "amount": a.get("amount"),
                    "label": a.get("label"), "status": a.get("status")} for a in alerts],
        forecast={
            "months": forecast.months, "income": forecast.income.values, "expense": forecast.expense.values,
            "balance": forecast.balance, "method": forecast.method,
        } if forecast else None,
        recommendations=recommendations[:6],
        has_data=not df.empty,
    )
    insight_repository.save_report_record(user_id, period, {
        "income": summary.income, "expenses": summary.expenses, "savings": summary.savings,
        "health_score": report.health["score"],
    })
    return report


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_html(report: FinancialReport) -> str:
    s = report.summary
    cards = "".join(
        f'<div class="card"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div></div>'
        for k, v in [
            ("Income", format_inr(s["income"])), ("Expenses", format_inr(s["expenses"])),
            ("Savings", format_inr(s["savings"])), ("Savings rate", format_percent(s["savings_rate"])),
            ("Investments", format_inr(s["investments"])), ("Tracked cash", format_inr(s["balance"])),
        ]
    )
    cat_rows = "".join(
        f"<tr><td>{_e(c['category'])}</td><td class='n'>{format_inr(c['amount'])}</td><td class='n'>{c['share']:.1f}%</td></tr>"
        for c in report.top_categories
    ) or "<tr><td colspan='3'>No expenses in this period.</td></tr>"
    monthly_rows = "".join(
        f"<tr><td>{_e(m['month'])}</td><td class='n'>{format_inr(m['income'])}</td><td class='n'>{format_inr(m['expense'])}</td>"
        f"<td class='n'>{format_inr(m['investment'])}</td><td class='n'>{format_inr(m['savings'])}</td></tr>"
        for m in report.monthly
    )
    budget_rows = "".join(
        f"<tr><td>{_e(b['category'])}</td><td class='n'>{format_inr(b['budget'])}</td><td class='n'>{format_inr(b['spent'])}</td>"
        f"<td class='n'>{format_inr(b['remaining'])}</td><td class='n {b['status']}'>{b['percent']:.0f}%</td></tr>"
        for b in report.budgets
    ) or "<tr><td colspan='5'>No budgets set.</td></tr>"
    factor_rows = "".join(
        f"<tr><td>{_e(f['name'])}</td><td>{_e(f['value'])}</td><td class='n'>{f['score']}/100</td></tr>"
        for f in report.health["factors"]
    )
    anomaly_rows = "".join(
        f"<tr><td>{_e(a['date'])}</td><td>{_e(a['description'])}</td><td class='n'>{format_inr(a['amount'])}</td>"
        f"<td>{_e(a['label'])}</td><td>{_e(a['status'])}</td></tr>"
        for a in report.anomalies
    ) or "<tr><td colspan='5'>No potentially unusual transactions flagged.</td></tr>"
    forecast_rows = ""
    if report.forecast:
        f = report.forecast
        forecast_rows = "".join(
            f"<tr><td>{_e(m)}</td><td class='n'>{format_inr(i)}</td><td class='n'>{format_inr(e)}</td><td class='n'>{format_inr(b)}</td></tr>"
            for m, i, e, b in zip(f["months"], f["income"], f["expense"], f["balance"])
        )
    recs = "".join(f"<li>{_e(r)}</li>" for r in report.recommendations) or "<li>Add more data for recommendations.</li>"
    score = report.health["score"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinTwin AI report - {_e(report.period_label)}</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;color:#13203a;margin:0;background:#f4f6fb}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 24px}}
 header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid #3EE6B0;padding-bottom:16px}}
 h1{{margin:0;font-size:26px}} h2{{font-size:18px;margin:32px 0 12px}}
 .muted{{color:#5d6b86;font-size:13px}}
 .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}}
 .card{{background:#fff;border-radius:12px;padding:14px 16px;border:1px solid #e2e7f1}}
 .k{{font-size:12px;color:#5d6b86}} .v{{font-size:20px;font-weight:700;margin-top:4px}}
 table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:14px}}
 th,td{{padding:9px 12px;border-bottom:1px solid #edf0f6;text-align:left}} th{{background:#eef2fa;font-weight:600}}
 .n{{text-align:right;font-variant-numeric:tabular-nums}} .exceeded{{color:#d23a4c;font-weight:700}} .warning{{color:#b7791f;font-weight:700}}
 .score{{font-size:40px;font-weight:800;color:#2a3a8f}}
 .note{{background:#fff8e6;border:1px solid #f3d38b;border-radius:10px;padding:12px 14px;font-size:13px;margin-top:28px}}
 @media print{{body{{background:#fff}} .card,table{{border:1px solid #ddd}}}}
 @media (max-width:640px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body><div class="wrap">
<header><div><h1>💰 FinTwin AI · Financial report</h1><div class="muted">{_e(report.user_name)} · {_e(report.period_label)}</div></div>
<div class="muted">Generated {_e(report.generated_at)}</div></header>
<h2>Financial summary</h2><div class="grid">{cards}</div>
<h2>Monthly breakdown</h2><table><tr><th>Month</th><th class="n">Income</th><th class="n">Expenses</th><th class="n">Investments</th><th class="n">Savings</th></tr>{monthly_rows}</table>
<h2>Top expense categories</h2><table><tr><th>Category</th><th class="n">Amount</th><th class="n">Share</th></tr>{cat_rows}</table>
<h2>Budget performance (this month)</h2><table><tr><th>Category</th><th class="n">Budget</th><th class="n">Spent</th><th class="n">Remaining</th><th class="n">Used</th></tr>{budget_rows}</table>
<h2>Financial health indicator</h2>
<p><span class="score">{_e(score) if score is not None else "—"}</span> <span class="muted">/ 100 · {_e(report.health['band'])}</span></p>
<table><tr><th>Factor</th><th>Your value</th><th class="n">Sub-score</th></tr>{factor_rows}</table>
<h2>Potential anomalies</h2><table><tr><th>Date</th><th>Description</th><th class="n">Amount</th><th>Flag</th><th>Status</th></tr>{anomaly_rows}</table>
{"<h2>Cash-flow forecast (" + _e(report.forecast['method']) + ")</h2><table><tr><th>Month</th><th class='n'>Income</th><th class='n'>Expenses</th><th class='n'>Projected cash</th></tr>" + forecast_rows + "</table>" if report.forecast else ""}
<h2>Recommendations</h2><ul>{recs}</ul>
<div class="note">This report is generated by FinTwin AI, an educational analysis tool. Scores, forecasts and anomaly flags are
estimates based on your recorded data and stated assumptions. They are not financial advice or proof of fraud.</div>
<p class="muted">Report period: {_e(report.period_label)} · Data as of {_e(format_date(utcnow()))}</p>
</div></body></html>"""
