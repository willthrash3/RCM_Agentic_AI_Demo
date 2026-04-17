"""AR Analytics Agent — KPI monitoring, anomaly detection, alerts.

KPIs (PRD §4.8 table):
- Days in AR / First Pass Rate / Denial Rate / Net Collection Rate
- AR > 90 Days / Charge Lag / Appeal Overturn Rate / Auth Denial Rate

Each KPI has a target and an alert threshold. Breach → emit kpi.alert event.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.agents.base import BaseAgent
from app.utils.time import get_demo_today
from app.agents.event_bus import emit
from app.database import locked
from app.models.agent import AgentInput, AgentOutput
from app.tools.analytics_tools import (
    compute_cash_forecast,
    get_ar_aging_snapshot,
    get_denial_rate_by_payer,
    get_first_pass_rate,
    write_analytics_alert,
)


KPI_CONFIG = [
    # name, target, alert_threshold, direction (good direction): 'down' means lower is better
    {"name": "days_in_ar", "label": "Days in AR", "target": 45, "alert": 55, "direction": "down", "unit": "days"},
    {"name": "first_pass_rate", "label": "First Pass Rate", "target": 0.94, "alert": 0.90, "direction": "up", "unit": "%"},
    {"name": "denial_rate", "label": "Denial Rate", "target": 0.08, "alert": 0.12, "direction": "down", "unit": "%"},
    {"name": "net_collection_rate", "label": "Net Collection Rate", "target": 0.96, "alert": 0.93, "direction": "up", "unit": "%"},
    {"name": "ar_over_90", "label": "AR > 90 Days", "target": 0.15, "alert": 0.20, "direction": "down", "unit": "%"},
    {"name": "charge_lag", "label": "Avg Charge Lag (days)", "target": 2.5, "alert": 4.0, "direction": "down", "unit": "days"},
    {"name": "appeal_overturn_rate", "label": "Appeal Overturn Rate", "target": 0.55, "alert": 0.40, "direction": "up", "unit": "%"},
    {"name": "open_hitl_tasks", "label": "Open HITL Tasks", "target": 10, "alert": 25, "direction": "down", "unit": "tasks"},
]


SYSTEM = """You are an AR analytics agent. Review the KPI snapshot and write a narrative
insight (3-5 sentences) highlighting deteriorations, recent improvements, and any
systemic patterns (e.g., payer-specific denials). Return JSON:
{
  "narrative": string,
  "alerts_raised": number,
  "recommended_actions": [string],
  "_reasoning": string
}
"""


class AnalyticsAgent(BaseAgent):
    name = "analytics_agent"

    def _current_value(self, metric: str) -> float:
        if metric == "first_pass_rate":
            return get_first_pass_rate(30)
        with locked() as conn:
            if metric == "days_in_ar":
                row = conn.execute(
                    """SELECT SUM(total_ar * days_in_ar) / NULLIF(SUM(total_ar), 0)
                         FROM ar_aging_snapshot
                        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM ar_aging_snapshot)"""
                ).fetchone()
                return float(row[0]) if row and row[0] else 0.0
            if metric == "denial_rate":
                row = conn.execute(
                    """SELECT COUNT(*) FILTER (WHERE claim_status = 'Denied')::DOUBLE /
                              NULLIF(COUNT(*) FILTER (WHERE claim_status IN ('Submitted','Paid','Denied')), 0)
                         FROM claims WHERE submission_date >= ?""",
                    (get_demo_today() - timedelta(days=30),),
                ).fetchone()
                return float(row[0]) if row and row[0] else 0.0
            if metric == "net_collection_rate":
                row = conn.execute(
                    """SELECT SUM(total_paid)::DOUBLE /
                              NULLIF(SUM(total_billed - COALESCE(total_allowed, 0) * 1.0), 0)
                         FROM claims WHERE submission_date >= ?""",
                    (get_demo_today() - timedelta(days=30),),
                ).fetchone()
                v = float(row[0]) if row and row[0] else 0.0
                return min(1.0, v)
            if metric == "ar_over_90":
                row = conn.execute(
                    """SELECT SUM(bucket_91_120 + bucket_over_120)::DOUBLE / NULLIF(SUM(total_ar), 0)
                         FROM ar_aging_snapshot
                        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM ar_aging_snapshot)"""
                ).fetchone()
                return float(row[0]) if row and row[0] else 0.0
            if metric == "charge_lag":
                row = conn.execute(
                    """SELECT AVG(charge_lag_days)::DOUBLE FROM encounters
                        WHERE service_date >= ?""",
                    (get_demo_today() - timedelta(days=30),),
                ).fetchone()
                return float(row[0]) if row and row[0] else 0.0
            if metric == "appeal_overturn_rate":
                row = conn.execute(
                    """SELECT COUNT(*) FILTER (WHERE overturn_flag)::DOUBLE /
                              NULLIF(COUNT(*) FILTER (WHERE appeal_submitted_at IS NOT NULL), 0)
                         FROM denials"""
                ).fetchone()
                return float(row[0]) if row and row[0] else 0.0
            if metric == "open_hitl_tasks":
                row = conn.execute(
                    "SELECT COUNT(*) FROM hitl_tasks WHERE status = 'pending'"
                ).fetchone()
                return float(row[0]) if row else 0.0
        return 0.0

    def _status_for(self, cfg: dict, value: float) -> str:
        target = cfg["target"]; alert = cfg["alert"]
        if cfg["direction"] == "down":
            if value <= target: return "On Track"
            if value >= alert: return "Alert"
            return "Watch"
        else:
            if value >= target: return "On Track"
            if value <= alert: return "Alert"
            return "Watch"

    async def run(self, input: AgentInput) -> AgentOutput:
        await self.started(input, summary="Computing KPI snapshot and alerts")

        cards = []
        alerts_raised = 0
        affected = []

        for cfg in KPI_CONFIG:
            value = self._current_value(cfg["name"])
            status = self._status_for(cfg, value)
            cards.append({
                "name": cfg["label"], "value": value, "target": cfg["target"],
                "status": status, "direction": cfg["direction"], "unit": cfg["unit"],
            })
            if status == "Alert":
                alerts_raised += 1
                write_analytics_alert(cfg["name"], "critical",
                                      f"{cfg['label']} at {value:.2f} — exceeds alert threshold of {cfg['alert']}",
                                      [])
                affected.append(cfg["name"])
                await emit(
                    "kpi.alert",
                    agent_name=self.name,
                    entity_type="kpi", entity_id=cfg["name"],
                    data={"metric": cfg["label"], "value": value, "threshold": cfg["alert"]},
                    task_id=self.task_id,
                )

        denial_by_payer = get_denial_rate_by_payer(30)
        await self.tool_call("system", "all", "get_denial_rate_by_payer", {"days": 30},
                             f"{len(denial_by_payer)} payers")
        aging = get_ar_aging_snapshot()
        await self.tool_call("system", "all", "get_ar_aging_snapshot", {},
                             f"total_ar={aging.get('total_ar', 0):.0f}")
        forecast = compute_cash_forecast(90)

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"KPI snapshot: {cards}\n"
                f"Denial rate by payer: {denial_by_payer}\n"
                f"AR aging snapshot total: ${aging.get('total_ar', 0):.0f}\n"
                f"Alerts raised this run: {alerts_raised}"
            ),
            entity_type="system", entity_id="all",
            fallback={
                "narrative": (
                    f"Current AR totals ${aging.get('total_ar', 0):.0f} with overall Days in AR at "
                    f"{aging.get('overall_days_in_ar', 0):.1f}. "
                    f"{alerts_raised} KPI threshold breach(es) were raised this run. "
                    "Monitor denials by payer — the top offender is in the denial_rate_by_payer table."
                ),
                "alerts_raised": alerts_raised,
                "recommended_actions": [
                    "Drill into highest-denial payer",
                    "Review aged claims >90 days",
                    "Check HITL queue volume",
                ],
                "_reasoning": "Rule-based KPI computation across all metrics.",
            },
        )

        output = AgentOutput(
            status="complete",
            result={
                "kpi_cards": cards,
                "alerts_raised": alerts_raised,
                "narrative": decision.get("narrative", ""),
                "denial_rate_by_payer": denial_by_payer,
                "aging_snapshot": aging,
                "cash_forecast": forecast,
                "recommended_actions": decision.get("recommended_actions", []),
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.95, hitl_required=False,
        )
        await self.completed(input, output)
        return output
