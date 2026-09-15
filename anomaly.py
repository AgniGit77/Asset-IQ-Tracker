"""Anomaly detection service — IsolationForest on equipment telemetry."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import numpy as np
from app.models import Equipment, UsageLog, AssetEvent, Alert, Rental
from app.services.utilization import compute_utilization
from datetime import datetime, timedelta


async def detect_anomalies(db: AsyncSession) -> list[dict]:
    """Run IsolationForest anomaly detection across the fleet.
    
    Features per asset:
    - utilization_score (0-100)
    - idle_ratio (idle / total hours)
    - fuel_per_engine_hour
    - days_since_last_event
    - is_assigned (0 or 1)
    """
    equipments = (await db.execute(select(Equipment))).scalars().all()
    if not equipments:
        return []

    feature_matrix = []
    eq_list = []
    now = datetime.utcnow()

    for eq in equipments:
        util = await compute_utilization(db, eq.id)
        
        total_engine = util["total_engine_hours"]
        total_idle = util["total_idle_hours"]
        total_fuel = util.get("total_fuel", 0)
        
        # idle ratio
        total_h = total_engine + total_idle
        idle_ratio = (total_idle / total_h) if total_h > 0 else 1.0
        
        # fuel per engine hour
        fuel_per_eh = (total_fuel / total_engine) if total_engine > 0 else 0.0
        
        # days since last event
        latest = (await db.execute(
            select(AssetEvent)
            .where(AssetEvent.equipment_id == eq.id)
            .order_by(AssetEvent.timestamp.desc())
            .limit(1)
        )).scalars().first()
        
        days_since = (now - latest.timestamp).days if latest else 999
        
        # is assigned
        is_assigned = 1.0
        if latest and latest.event_type in ("checkin", "received", "maintenance"):
            is_assigned = 0.0
        elif not latest:
            is_assigned = 0.0

        features = [
            util["utilization_score"],
            idle_ratio * 100,
            fuel_per_eh,
            float(days_since),
            is_assigned * 100,
        ]
        feature_matrix.append(features)
        eq_list.append(eq)

    if len(feature_matrix) < 3:
        return []

    # Run IsolationForest
    try:
        from sklearn.ensemble import IsolationForest
        
        X = np.array(feature_matrix)
        model = IsolationForest(
            n_estimators=100,
            contamination=0.3,  # expect ~30% anomalies in our small fleet
            random_state=42,
        )
        predictions = model.fit_predict(X)
        scores = model.decision_function(X)
    except Exception:
        # Fallback: simple threshold-based detection
        predictions = []
        scores = []
        for f in feature_matrix:
            is_anomaly = (f[0] < 30 or f[1] > 60 or f[3] > 10 or f[4] < 50)
            predictions.append(-1 if is_anomaly else 1)
            scores.append(-0.5 if is_anomaly else 0.5)

    anomalies = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        eq = eq_list[i]
        features = feature_matrix[i]
        
        if pred == -1:  # anomaly
            # Determine anomaly reason
            reasons = []
            if features[4] < 50:
                reasons.append("unassigned equipment generating zero revenue")
            if features[0] < 30:
                reasons.append(f"critically low utilization ({features[0]:.0f}%)")
            if features[1] > 55:
                reasons.append(f"excessive idle time ({features[1]:.0f}% idle ratio)")
            if features[2] > 20:
                reasons.append(f"abnormal fuel burn ({features[2]:.1f} L/engine-hr)")
            if features[3] > 10:
                reasons.append(f"no activity for {features[3]:.0f} days")
            
            if not reasons:
                reasons.append("anomalous operating pattern detected")
            
            severity = "critical" if score < -0.3 else "high" if score < -0.1 else "medium"
            
            anomalies.append({
                "equipment_id": eq.equipment_id,
                "equipment_name": eq.name,
                "anomaly_score": round(float(score), 3),
                "severity": severity,
                "reasons": reasons,
                "features": {
                    "utilization": round(features[0], 1),
                    "idle_ratio": round(features[1], 1),
                    "fuel_per_eh": round(features[2], 1),
                    "days_inactive": round(features[3], 0),
                    "assigned": features[4] > 50,
                },
            })

    # Persist new alerts for anomalies
    for a in anomalies:
        eq = (await db.execute(
            select(Equipment).where(Equipment.equipment_id == a["equipment_id"])
        )).scalars().first()
        if eq:
            existing_alert = (await db.execute(
                select(Alert)
                .where(Alert.equipment_id == eq.id)
                .where(Alert.alert_type == "anomaly")
                .where(Alert.is_resolved == False)
            )).scalars().first()
            if not existing_alert:
                db.add(Alert(
                    equipment_id=eq.id,
                    alert_type="anomaly",
                    severity=a["severity"],
                    message=f"Anomaly detected: {'; '.join(a['reasons'])}",
                ))
    await db.commit()

    return anomalies
