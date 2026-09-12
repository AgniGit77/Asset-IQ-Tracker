"""Asset timeline service — 5-horizon forward projection per asset."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from app.models import Equipment, AssetEvent, Rental, UsageLog, Alert
from app.services.utilization import compute_utilization


async def compute_timeline(db: AsyncSession, equipment_db_id: int) -> dict:
    """Generate a 5-horizon forward projection for an asset.
    
    Horizons:
    1. Now — latest event status
    2. Next 2 hours — idle trend extrapolation
    3. Tonight — return due date check
    4. Tomorrow — engine-hour maintenance threshold
    5. Next week — site demand forecast
    """
    eq = await db.get(Equipment, equipment_db_id)
    if not eq:
        return {}

    now = datetime.utcnow()
    
    # Get latest event
    latest_event = (await db.execute(
        select(AssetEvent)
        .where(AssetEvent.equipment_id == eq.id)
        .order_by(AssetEvent.timestamp.desc())
        .limit(1)
    )).scalars().first()
    
    # Get active rental
    active_rental = (await db.execute(
        select(Rental)
        .where(Rental.equipment_id == eq.id)
        .where(Rental.status.in_(["active", "overdue"]))
        .order_by(Rental.start_date.desc())
        .limit(1)
    )).scalars().first()
    
    # Get utilization
    util = await compute_utilization(db, eq.id)
    
    # Get recent usage logs (last 7 days)
    week_ago = now - timedelta(days=7)
    recent_logs = (await db.execute(
        select(UsageLog)
        .where(UsageLog.equipment_id == eq.id)
        .where(UsageLog.date >= week_ago)
        .order_by(UsageLog.date.desc())
    )).scalars().all()
    
    horizons = []
    
    # ── HORIZON 1: NOW ──────────────────────────────────
    if latest_event:
        event_map = {
            "checkout": ("Operating", "Equipment is checked out and active on site", "green"),
            "assign": ("Assigned", "Equipment assigned to operator on site", "green"),
            "usage_log": ("Active", "Equipment actively logging usage data", "green"),
            "checkin": ("Available", "Equipment checked in and available for deployment", "gray"),
            "maintenance": ("Under Maintenance", "Equipment undergoing scheduled maintenance", "amber"),
            "received": ("Awaiting Assignment", "Equipment received but not yet assigned", "red"),
            "anomaly_flagged": ("Anomaly Detected", "Unusual operating pattern flagged", "red"),
            "reallocation": ("Being Reallocated", "Equipment in transit to new assignment", "amber"),
        }
        title, desc, status = event_map.get(
            latest_event.event_type,
            ("Unknown", "Status unclear", "gray")
        )
    else:
        title, desc, status = "No Data", "No events recorded for this asset", "gray"
    
    horizons.append({
        "horizon": "now",
        "label": "Right Now",
        "icon": "activity",
        "status": status,
        "title": title,
        "description": desc,
        "confidence": 1.0,
    })
    
    # ── HORIZON 2: NEXT 2 HOURS ─────────────────────────
    if recent_logs:
        avg_idle = sum(l.idle_hours for l in recent_logs) / len(recent_logs)
        avg_engine = sum(l.engine_hours for l in recent_logs) / len(recent_logs)
        
        if avg_idle > avg_engine * 0.6:
            h2_title = "Likely Idling"
            h2_desc = f"Trending toward idle — avg {avg_idle:.1f}h idle vs {avg_engine:.1f}h engine per day"
            h2_status = "amber"
        elif avg_engine > 7:
            h2_title = "High Activity Expected"
            h2_desc = f"Strong utilization trend — {avg_engine:.1f}h engine hours/day average"
            h2_status = "green"
        else:
            h2_title = "Moderate Activity"
            h2_desc = f"Normal operating pattern — {avg_engine:.1f}h engine/day"
            h2_status = "green"
    else:
        h2_title = "No Activity Expected"
        h2_desc = "No recent usage data — equipment may be idle"
        h2_status = "red" if status != "gray" else "gray"
    
    horizons.append({
        "horizon": "next_2h",
        "label": "Next 2 Hours",
        "icon": "clock",
        "status": h2_status,
        "title": h2_title,
        "description": h2_desc,
        "confidence": 0.85,
    })
    
    # ── HORIZON 3: TONIGHT ──────────────────────────────
    if active_rental and active_rental.expected_return:
        days_until_return = (active_rental.expected_return - now).days
        if days_until_return < 0:
            h3_title = "OVERDUE Return"
            h3_desc = f"Return was due {abs(days_until_return)} days ago — requires immediate action"
            h3_status = "red"
        elif days_until_return == 0:
            h3_title = "Return Due Today"
            h3_desc = "Equipment scheduled for return today — prepare check-in"
            h3_status = "amber"
        elif days_until_return <= 3:
            h3_title = "Return Approaching"
            h3_desc = f"Return due in {days_until_return} days — schedule check-in inspection"
            h3_status = "amber"
        else:
            h3_title = "On Schedule"
            h3_desc = f"Return in {days_until_return} days — no action needed tonight"
            h3_status = "green"
    else:
        h3_title = "No Active Rental"
        h3_desc = "No rental contract active — equipment available for assignment"
        h3_status = "gray"
    
    horizons.append({
        "horizon": "tonight",
        "label": "Tonight",
        "icon": "moon",
        "status": h3_status,
        "title": h3_title,
        "description": h3_desc,
        "confidence": 0.9,
    })
    
    # ── HORIZON 4: TOMORROW ─────────────────────────────
    # Maintenance threshold: flag if total engine hours > threshold
    total_engine = util["total_engine_hours"]
    maintenance_threshold = 500  # hours
    next_maintenance = maintenance_threshold - (total_engine % maintenance_threshold)
    
    if next_maintenance < 20:
        h4_title = "Maintenance Due"
        h4_desc = f"Only {next_maintenance:.0f} engine hours until next scheduled service"
        h4_status = "red"
    elif next_maintenance < 50:
        h4_title = "Maintenance Approaching"
        h4_desc = f"{next_maintenance:.0f} engine hours until next service — plan ahead"
        h4_status = "amber"
    else:
        h4_title = "Maintenance Clear"
        h4_desc = f"{next_maintenance:.0f} engine hours until next service interval"
        h4_status = "green"
    
    horizons.append({
        "horizon": "tomorrow",
        "label": "Tomorrow",
        "icon": "sun",
        "status": h4_status,
        "title": h4_title,
        "description": h4_desc,
        "confidence": 0.75,
    })
    
    # ── HORIZON 5: NEXT WEEK ────────────────────────────
    # Site demand forecast
    if active_rental and active_rental.site_id:
        from app.models import Site
        site = await db.get(Site, active_rental.site_id)
        if site:
            if site.demand_level == "high":
                h5_title = "High Demand Continues"
                h5_desc = f"{site.name} forecasts sustained high demand — keep deployed"
                h5_status = "green"
            elif site.demand_level == "medium":
                h5_title = "Steady Demand"
                h5_desc = f"{site.name} demand is stable — monitor utilization"
                h5_status = "green"
            else:
                h5_title = "Demand Declining"
                h5_desc = f"{site.name} demand is low — consider reallocation"
                h5_status = "amber"
        else:
            h5_title = "Unknown Forecast"
            h5_desc = "Unable to determine site demand outlook"
            h5_status = "gray"
    else:
        h5_title = "Reallocation Opportunity"
        h5_desc = "Unassigned equipment — high-demand sites need this asset type"
        h5_status = "red" if util["utilization_score"] < 10 else "amber"
    
    horizons.append({
        "horizon": "next_week",
        "label": "Next Week",
        "icon": "calendar",
        "status": h5_status,
        "title": h5_title,
        "description": h5_desc,
        "confidence": 0.6,
    })
    
    return {
        "equipment_id": eq.equipment_id,
        "equipment_name": eq.name,
        "horizons": horizons,
    }
