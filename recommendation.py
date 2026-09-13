"""Recommendation engine — demand-to-asset matching layer."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.models import Equipment, Site, Recommendation, AssetEvent, Rental, Alert
from app.services.utilization import compute_utilization
from app.services.forecast import forecast_demand


async def generate_recommendations(db: AsyncSession) -> list[dict]:
    """Cross-reference under-utilized assets against predicted demand.
    
    Logic:
    1. Find under-utilized assets (util < 40%) or unassigned assets
    2. Get demand forecasts for all sites
    3. Match idle assets to sites with unmet demand
    4. Generate specific reallocation suggestions
    """
    equipments = (await db.execute(select(Equipment))).scalars().all()
    sites = (await db.execute(select(Site))).scalars().all()
    
    # Find under-utilized or idle assets
    idle_assets = []
    for eq in equipments:
        util = await compute_utilization(db, eq.id)
        
        # Get latest event to determine current status
        latest = (await db.execute(
            select(AssetEvent)
            .where(AssetEvent.equipment_id == eq.id)
            .order_by(AssetEvent.timestamp.desc())
            .limit(1)
        )).scalars().first()
        
        is_available = True
        current_site_id = None
        if latest:
            if latest.event_type == "maintenance":
                is_available = False
            current_site_id = latest.site_id
        
        if is_available and (util["utilization_score"] < 40 or 
                             latest is None or 
                             latest.event_type in ("checkin", "received")):
            idle_assets.append({
                "equipment": eq,
                "util": util,
                "current_site_id": current_site_id,
                "latest_event": latest,
            })
    
    # Get demand forecasts
    forecasts = await forecast_demand(db)
    
    # Match idle assets to high-demand sites
    recommendations = []
    used_assets = set()
    
    for forecast in forecasts:
        if forecast["gap"] <= 0:
            continue
        
        for asset_info in idle_assets:
            eq = asset_info["equipment"]
            if eq.id in used_assets:
                continue
            if eq.type != forecast["equipment_type"]:
                continue
            if asset_info["current_site_id"] == forecast["site_id"]:
                continue
            
            # Calculate projected improvement
            current_util = asset_info["util"]["utilization_score"]
            # Estimate new utilization based on site demand level
            demand_bonus = {"high": 40, "medium": 25, "low": 10}.get(
                forecast["demand_level"], 15
            )
            projected_util = min(current_util + demand_bonus, 95)
            improvement = projected_util - current_util
            
            # Get site name
            site = (await db.get(Site, forecast["site_id"]))
            
            weekly_value = round(eq.rental_rate_per_hour * improvement / 100 * 8 * 7, 0)  # 8h/day, 7 days
            
            reason = (
                f"{eq.equipment_id} is {'idle and unassigned' if current_util < 5 else f'under-utilized at {current_util:.0f}%'}. "
                f"{site.name} has {'high' if forecast['demand_level'] == 'high' else 'unmet'} demand for {eq.type}s. "
                f"Reallocating would add ₹{weekly_value:,.0f}/week in utilization value."
            )
            
            recommendations.append({
                "equipment": eq,
                "target_site": site,
                "action": "reallocate",
                "reason": reason,
                "projected_improvement": round(improvement, 1),
            })
            used_assets.add(eq.id)
            break
    
    # Persist recommendations
    new_recs = []
    for rec in recommendations:
        # Check if similar recommendation already exists
        existing = (await db.execute(
            select(Recommendation)
            .where(Recommendation.equipment_id == rec["equipment"].id)
            .where(Recommendation.is_applied == False)
            .where(Recommendation.action == rec["action"])
        )).scalars().first()
        
        if not existing:
            new_rec = Recommendation(
                equipment_id=rec["equipment"].id,
                target_site_id=rec["target_site"].id if rec["target_site"] else None,
                action=rec["action"],
                reason=rec["reason"],
                projected_improvement=rec["projected_improvement"],
            )
            db.add(new_rec)
            new_recs.append(new_rec)
    
    await db.commit()
    
    # Return all active recommendations
    all_recs = (await db.execute(
        select(Recommendation).where(Recommendation.is_applied == False)
    )).scalars().all()
    
    result = []
    for r in all_recs:
        eq = await db.get(Equipment, r.equipment_id)
        site = await db.get(Site, r.target_site_id) if r.target_site_id else None
        result.append({
            "id": r.id,
            "equipment_id": r.equipment_id,
            "equipment_code": eq.equipment_id if eq else "",
            "equipment_name": eq.name if eq else "",
            "target_site_id": r.target_site_id,
            "target_site_name": site.name if site else None,
            "action": r.action,
            "reason": r.reason,
            "projected_improvement": r.projected_improvement,
            "is_applied": r.is_applied,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    
    return result


async def apply_recommendation(db: AsyncSession, rec_id: int) -> dict:
    """Apply a recommendation — execute the suggested action.
    
    For 'reallocate': create checkout + assign events, update rental.
    """
    rec = await db.get(Recommendation, rec_id)
    if not rec:
        return {"error": "Recommendation not found"}
    if rec.is_applied:
        return {"error": "Already applied"}
    
    eq = await db.get(Equipment, rec.equipment_id)
    site = await db.get(Site, rec.target_site_id) if rec.target_site_id else None
    
    now = datetime.utcnow()
    
    if rec.action == "reallocate" and site:
        # Create checkout event
        db.add(AssetEvent(
            equipment_id=eq.id,
            event_type="checkout",
            timestamp=now,
            site_id=site.id,
            event_metadata={"reason": "AI recommendation applied", "recommendation_id": rec.id},
            gps_lat=site.lat,
            gps_lng=site.lng,
        ))
        
        # Create assign event
        db.add(AssetEvent(
            equipment_id=eq.id,
            event_type="assign",
            timestamp=now,
            site_id=site.id,
            event_metadata={"reason": "AI recommendation applied"},
            gps_lat=site.lat,
            gps_lng=site.lng,
        ))
        
        # Create rental
        db.add(Rental(
            equipment_id=eq.id,
            site_id=site.id,
            start_date=now,
            expected_return=now + __import__("datetime").timedelta(days=30),
            status="active",
        ))
    
    # Mark recommendation as applied
    rec.is_applied = True
    rec.applied_at = now
    
    # Resolve related alerts
    alerts = (await db.execute(
        select(Alert)
        .where(Alert.equipment_id == eq.id)
        .where(Alert.is_resolved == False)
    )).scalars().all()
    
    for alert in alerts:
        if alert.alert_type in ("unassigned", "low_utilization"):
            alert.is_resolved = True
            alert.resolved_at = now
    
    await db.commit()
    
    return {
        "status": "applied",
        "equipment_id": eq.equipment_id,
        "equipment_name": eq.name,
        "action": rec.action,
        "target_site": site.name if site else None,
        "projected_improvement": rec.projected_improvement,
    }
