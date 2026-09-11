"""Utilization scoring service — the core metric engine."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Equipment, UsageLog, CostConfig


async def compute_utilization(db: AsyncSession, equipment_db_id: int) -> dict:
    """Compute utilization score for an asset from its usage logs.
    
    Formula: engine_hours / (engine_hours + idle_hours) × 100
    """
    result = await db.execute(
        select(
            func.sum(UsageLog.engine_hours).label("total_engine"),
            func.sum(UsageLog.idle_hours).label("total_idle"),
            func.sum(UsageLog.fuel_consumed).label("total_fuel"),
            func.count(UsageLog.id).label("log_count"),
        ).where(UsageLog.equipment_id == equipment_db_id)
    )
    row = result.one()
    
    total_engine = float(row.total_engine or 0)
    total_idle = float(row.total_idle or 0)
    total_fuel = float(row.total_fuel or 0)
    
    total_hours = total_engine + total_idle
    score = (total_engine / total_hours * 100) if total_hours > 0 else 0.0
    
    if score >= 70:
        status = "green"
    elif score >= 40:
        status = "amber"
    else:
        status = "red"
    
    return {
        "total_engine_hours": round(total_engine, 1),
        "total_idle_hours": round(total_idle, 1),
        "total_fuel": round(total_fuel, 1),
        "utilization_score": round(score, 1),
        "status": status,
        "log_count": row.log_count or 0,
    }


async def compute_all_utilizations(db: AsyncSession) -> list[dict]:
    """Compute utilization for every asset in the fleet."""
    equipments = (await db.execute(select(Equipment))).scalars().all()
    results = []
    for eq in equipments:
        util = await compute_utilization(db, eq.id)
        util["equipment_id"] = eq.equipment_id
        util["equipment_name"] = eq.name
        results.append(util)
    return results


async def get_idle_loss(db: AsyncSession, equipment_db_id: int) -> dict:
    """Calculate idle loss for an asset.
    
    wasted_value = idle_hours × (rental_rate_per_hour + operator_cost_per_hour) 
                 + idle_fuel_burn × fuel_cost_per_litre
    """
    eq = await db.get(Equipment, equipment_db_id)
    if not eq:
        return {}

    config = (await db.execute(select(CostConfig))).scalars().first()
    if not config:
        config_vals = {"operator_cost": 350, "fuel_cost": 95, "idle_fuel_rate": 4.5}
    else:
        config_vals = {
            "operator_cost": config.operator_cost_per_hour,
            "fuel_cost": config.fuel_cost_per_litre,
            "idle_fuel_rate": config.idle_fuel_burn_rate,
        }

    util = await compute_utilization(db, equipment_db_id)
    idle_hours = util["total_idle_hours"]
    
    rental_cost_lost = idle_hours * eq.rental_rate_per_hour
    operator_cost_lost = idle_hours * config_vals["operator_cost"]
    fuel_cost_lost = idle_hours * config_vals["idle_fuel_rate"] * config_vals["fuel_cost"]
    total = rental_cost_lost + operator_cost_lost + fuel_cost_lost
    
    return {
        "equipment_id": eq.equipment_id,
        "equipment_name": eq.name,
        "idle_hours": round(idle_hours, 1),
        "rental_cost_lost": round(rental_cost_lost, 0),
        "operator_cost_lost": round(operator_cost_lost, 0),
        "fuel_cost_lost": round(fuel_cost_lost, 0),
        "total_wasted": round(total, 0),
        "period": "all_time",
    }


async def compute_fleet_efficiency(db: AsyncSession) -> dict:
    """Single 0–100 fleet efficiency score.
    
    Weighted: utilization (40%) + assignment coverage (30%) + overdue penalty (30%)
    """
    utils = await compute_all_utilizations(db)
    if not utils:
        return {"score": 0, "breakdown": {}, "trend": []}
    
    # Average utilization (0-100)
    avg_util = sum(u["utilization_score"] for u in utils) / len(utils)
    
    # Assignment coverage: % of assets that are assigned to a site
    from app.models import AssetEvent
    total = len(utils)
    assigned = 0
    for u in utils:
        eq = (await db.execute(
            select(Equipment).where(Equipment.equipment_id == u["equipment_id"])
        )).scalars().first()
        if eq:
            latest_event = (await db.execute(
                select(AssetEvent)
                .where(AssetEvent.equipment_id == eq.id)
                .order_by(AssetEvent.timestamp.desc())
                .limit(1)
            )).scalars().first()
            if latest_event and latest_event.event_type in ("checkout", "assign", "usage_log"):
                assigned += 1
    
    coverage = (assigned / total * 100) if total > 0 else 0
    
    # Overdue penalty
    from app.models import Rental
    overdue_count = (await db.execute(
        select(func.count(Rental.id)).where(Rental.status == "overdue")
    )).scalar() or 0
    overdue_penalty = min(overdue_count * 15, 100)  # each overdue costs 15 points, cap at 100
    
    score = (avg_util * 0.40) + (coverage * 0.30) + ((100 - overdue_penalty) * 0.30)
    
    return {
        "score": round(min(max(score, 0), 100), 1),
        "breakdown": {
            "utilization": round(avg_util, 1),
            "assignment_coverage": round(coverage, 1),
            "overdue_penalty": round(overdue_penalty, 1),
        },
        "trend": [],
    }
