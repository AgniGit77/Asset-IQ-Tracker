"""Pydantic schemas — request/response DTOs for all API endpoints."""
from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


# ── Equipment ──────────────────────────────────────────────
class EquipmentBase(BaseModel):
    equipment_id: str
    name: str
    type: str
    model: Optional[str] = None
    year: Optional[int] = None
    serial_number: Optional[str] = None
    rental_rate_per_hour: float = 0.0
    image_url: str = ""


class EquipmentOut(EquipmentBase):
    id: int
    created_at: datetime
    current_status: Optional[str] = None
    current_site: Optional[str] = None
    current_operator: Optional[str] = None
    utilization_score: Optional[float] = None
    risk_level: Optional[str] = None  # low, medium, high

    class Config:
        from_attributes = True


class EquipmentCreate(EquipmentBase):
    pass


# ── Site ───────────────────────────────────────────────────
class SiteOut(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    demand_level: str = "medium"

    class Config:
        from_attributes = True


# ── Operator ───────────────────────────────────────────────
class OperatorOut(BaseModel):
    id: int
    name: str
    license_number: Optional[str] = None
    certification: Optional[str] = None
    contact: Optional[str] = None

    class Config:
        from_attributes = True


# ── Lifecycle ──────────────────────────────────────────────
class CheckoutRequest(BaseModel):
    equipment_id: str
    site_id: int
    operator_id: int
    expected_return: Optional[datetime] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    notes: str = ""


class CheckinRequest(BaseModel):
    equipment_id: str
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    condition_notes: str = ""
    odometer: Optional[float] = None


class AssignRequest(BaseModel):
    equipment_id: str
    site_id: int
    operator_id: int
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


class UsageLogCreate(BaseModel):
    equipment_id: str
    date: Optional[datetime] = None
    engine_hours: float = 0.0
    idle_hours: float = 0.0
    fuel_consumed: float = 0.0
    operating_days: float = 1.0


# ── Events ─────────────────────────────────────────────────
class AssetEventOut(BaseModel):
    id: int
    equipment_id: int
    event_type: str
    timestamp: datetime
    site_id: Optional[int] = None
    operator_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="event_metadata")
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None

    class Config:
        from_attributes = True


# ── Alerts ─────────────────────────────────────────────────
class AlertOut(BaseModel):
    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    equipment_code: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Recommendations ────────────────────────────────────────
class RecommendationOut(BaseModel):
    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    equipment_code: Optional[str] = None
    target_site_id: Optional[int] = None
    target_site_name: Optional[str] = None
    action: str
    reason: str
    projected_improvement: float
    is_applied: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApplyRecommendationRequest(BaseModel):
    pass  # just needs the recommendation ID from URL


# ── Dashboard KPIs ─────────────────────────────────────────
class DashboardKPIs(BaseModel):
    total_assets: int = 0
    active_assets: int = 0
    underutilized_assets: int = 0
    unassigned_assets: int = 0
    overdue_assets: int = 0
    high_risk_assets: int = 0
    fleet_efficiency_score: float = 0.0
    total_idle_loss: float = 0.0


# ── Utilization ────────────────────────────────────────────
class UtilizationOut(BaseModel):
    equipment_id: str
    equipment_name: str
    total_engine_hours: float
    total_idle_hours: float
    utilization_score: float
    status: str  # green, amber, red
    idle_loss: float = 0.0


# ── Forecast ───────────────────────────────────────────────
class ForecastRequest(BaseModel):
    site_id: Optional[int] = None
    equipment_type: Optional[str] = None
    horizon_days: int = 30


class ForecastOut(BaseModel):
    site_name: str
    equipment_type: str
    horizon: str
    predicted_demand: float
    current_supply: int
    gap: float


# ── Timeline ───────────────────────────────────────────────
class TimelineHorizon(BaseModel):
    horizon: str  # now, next_2h, tonight, tomorrow, next_week
    label: str
    icon: str
    status: str  # green, amber, red, gray
    title: str
    description: str
    confidence: float = 0.0


class AssetTimeline(BaseModel):
    equipment_id: str
    equipment_name: str
    horizons: list[TimelineHorizon]


# ── Inspection ─────────────────────────────────────────────
class ZoneResult(BaseModel):
    zone: str
    damage_type: str
    severity: int  # 1-5
    description: str


class InspectionResult(BaseModel):
    equipment_id: str
    overall_score: float
    zone_results: list[ZoneResult]
    maintenance_ticket_filed: bool = False
    created_at: datetime


# ── Idle Loss ──────────────────────────────────────────────
class IdleLossOut(BaseModel):
    equipment_id: str
    equipment_name: str
    idle_hours: float
    rental_cost_lost: float
    operator_cost_lost: float
    fuel_cost_lost: float
    total_wasted: float
    period: str = "today"


# ── Fleet Efficiency ───────────────────────────────────────
class FleetEfficiency(BaseModel):
    score: float  # 0-100
    breakdown: dict[str, float] = {}
    trend: list[dict[str, Any]] = []
