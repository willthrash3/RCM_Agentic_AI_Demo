"""KPI / analytics models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

KPIStatus = Literal["On Track", "Watch", "Alert"]


class KPIDataPoint(BaseModel):
    date: date
    value: float


class KPITimeseries(BaseModel):
    metric: str
    points: list[KPIDataPoint]


class KPICard(BaseModel):
    name: str
    current_value: float
    target_value: float
    trend_7d: float = 0.0
    status: KPIStatus = "On Track"
    direction_good: Literal["up", "down"] = "down"
    unit: str = ""


class KPIDashboardSnapshot(BaseModel):
    as_of: datetime
    cards: list[KPICard]
    agent_activity_ticker: list[dict] = Field(default_factory=list)


class ARAgingBucket(BaseModel):
    payer_id: str
    bucket_0_30: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_91_120: Decimal
    bucket_over_120: Decimal
    total_ar: Decimal
    days_in_ar: float


class ARAgingSnapshot(BaseModel):
    snapshot_date: date
    buckets: list[ARAgingBucket]
    total_ar: Decimal
    overall_days_in_ar: float


class KPIAlert(BaseModel):
    alert_id: str
    alert_type: str
    severity: Literal["info", "warning", "critical"]
    description: str
    affected_entities: list[str] = Field(default_factory=list)
    created_at: datetime
    resolved_at: Optional[datetime] = None
