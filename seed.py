"""Seed database with 7 assets, sites, operators, and rich historical data."""
from __future__ import annotations
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import (
    Equipment, Site, Operator, Rental, UsageLog,
    AssetEvent, Alert, Recommendation, CostConfig,
)

random.seed(42)


async def seed_database(db: AsyncSession) -> None:
    """Seed all tables if empty."""
    count = await db.scalar(select(func.count(Equipment.id)))
    if count and count > 0:
        return  # already seeded

    # ── Sites ──────────────────────────────────────────
    sites = [
        Site(name="Mumbai Metro Construction", location="Mumbai, Maharashtra",
             lat=19.0760, lng=72.8777, demand_level="high"),
        Site(name="Delhi-Meerut Expressway", location="Delhi NCR",
             lat=28.7041, lng=77.1025, demand_level="high"),
        Site(name="Bangalore IT Park Phase 3", location="Bangalore, Karnataka",
             lat=12.9716, lng=77.5946, demand_level="medium"),
        Site(name="Chennai Port Expansion", location="Chennai, Tamil Nadu",
             lat=13.0827, lng=80.2707, demand_level="medium"),
        Site(name="Hyderabad Ring Road", location="Hyderabad, Telangana",
             lat=17.3850, lng=78.4867, demand_level="low"),
    ]
    db.add_all(sites)
    await db.flush()

    # ── Operators ──────────────────────────────────────
    operators = [
        Operator(name="Rajesh Kumar", license_number="DL-HMV-2019-4521",
                 certification="CAT Certified Operator", contact="+91-98765-43210"),
        Operator(name="Suresh Patel", license_number="GJ-HMV-2020-7834",
                 certification="Heavy Equipment License", contact="+91-87654-32109"),
        Operator(name="Amit Singh", license_number="MH-HMV-2018-2156",
                 certification="CAT Certified Operator", contact="+91-76543-21098"),
        Operator(name="Vikram Sharma", license_number="KA-HMV-2021-9087",
                 certification="Advanced Operator License", contact="+91-65432-10987"),
        Operator(name="Pradeep Joshi", license_number="TN-HMV-2020-3456",
                 certification="Heavy Equipment License", contact="+91-54321-09876"),
    ]
    db.add_all(operators)
    await db.flush()

    # ── Cost Config ────────────────────────────────────
    cost = CostConfig(
        operator_cost_per_hour=350.0,
        fuel_cost_per_litre=95.0,
        idle_fuel_burn_rate=4.5,
    )
    db.add(cost)
    await db.flush()

    # ── Equipment (7 assets) ───────────────────────────
    equipment_data = [
        {
            "equipment_id": "EQX1001", "name": "CAT 320 Excavator",
            "type": "Excavator", "model": "320 GC", "year": 2022,
            "serial_number": "CAT320GC22A001", "rental_rate_per_hour": 2500.0,
            "status": "active", "site_idx": 0, "operator_idx": 0,
            "util_profile": "healthy",
        },
        {
            "equipment_id": "EQX1002", "name": "CAT D6 Bulldozer",
            "type": "Bulldozer", "model": "D6 XE", "year": 2021,
            "serial_number": "CATD6XE21B002", "rental_rate_per_hour": 3200.0,
            "status": "active", "site_idx": 1, "operator_idx": 1,
            "util_profile": "high_idle",
        },
        {
            "equipment_id": "EQX1003", "name": "CAT 950 Wheel Loader",
            "type": "Wheel Loader", "model": "950 GC", "year": 2023,
            "serial_number": "CAT950GC23C003", "rental_rate_per_hour": 2800.0,
            "status": "overdue", "site_idx": 2, "operator_idx": 2,
            "util_profile": "moderate",
        },
        {
            "equipment_id": "EQX1004", "name": "CAT 740 Articulated Truck",
            "type": "Articulated Truck", "model": "740 GC", "year": 2020,
            "serial_number": "CAT740GC20D004", "rental_rate_per_hour": 2200.0,
            "status": "maintenance", "site_idx": None, "operator_idx": None,
            "util_profile": "low",
        },
        {
            "equipment_id": "EQX1005", "name": "CAT 336 Excavator",
            "type": "Excavator", "model": "336 GC", "year": 2022,
            "serial_number": "CAT336GC22E005", "rental_rate_per_hour": 2700.0,
            "status": "active", "site_idx": 3, "operator_idx": 3,
            "util_profile": "low",
        },
        {
            "equipment_id": "EQX1006", "name": "CAT CB13 Compactor",
            "type": "Compactor", "model": "CB13", "year": 2023,
            "serial_number": "CATCB1323F006", "rental_rate_per_hour": 1800.0,
            "status": "available", "site_idx": None, "operator_idx": None,
            "util_profile": "none",
        },
        {
            "equipment_id": "EQX1007", "name": "CAT 323 Excavator",
            "type": "Excavator", "model": "323 GC", "year": 2024,
            "serial_number": "CAT323GC24G007", "rental_rate_per_hour": 2600.0,
            "status": "unassigned", "site_idx": None, "operator_idx": None,
            "util_profile": "none",
        },
    ]

    now = datetime.utcnow()
    equipments = []

    for ed in equipment_data:
        eq = Equipment(
            equipment_id=ed["equipment_id"],
            name=ed["name"],
            type=ed["type"],
            model=ed["model"],
            year=ed["year"],
            serial_number=ed["serial_number"],
            rental_rate_per_hour=ed["rental_rate_per_hour"],
        )
        db.add(eq)
        await db.flush()
        equipments.append((eq, ed))

    # ── Generate history for each asset ────────────────
    for eq, ed in equipments:
        site_id = sites[ed["site_idx"]].id if ed["site_idx"] is not None else None
        operator_id = operators[ed["operator_idx"]].id if ed["operator_idx"] is not None else None
        profile = ed["util_profile"]

        # Generate 60 days of usage logs
        for day_offset in range(60, 0, -1):
            day = now - timedelta(days=day_offset)

            if profile == "healthy":
                engine_h = round(random.uniform(7.0, 10.0), 1)
                idle_h = round(random.uniform(0.5, 2.0), 1)
                fuel = round(engine_h * random.uniform(12.0, 16.0), 1)
            elif profile == "high_idle":
                engine_h = round(random.uniform(4.0, 6.0), 1)
                idle_h = round(random.uniform(4.0, 7.0), 1)
                fuel = round((engine_h + idle_h * 0.3) * random.uniform(14.0, 18.0), 1)
            elif profile == "moderate":
                engine_h = round(random.uniform(5.0, 8.0), 1)
                idle_h = round(random.uniform(1.5, 3.5), 1)
                fuel = round(engine_h * random.uniform(10.0, 14.0), 1)
            elif profile == "low":
                engine_h = round(random.uniform(1.0, 3.5), 1)
                idle_h = round(random.uniform(2.0, 5.0), 1)
                fuel = round(engine_h * random.uniform(10.0, 15.0), 1)
            else:  # none
                engine_h = 0.0
                idle_h = 0.0
                fuel = 0.0

            if profile != "none":
                log = UsageLog(
                    equipment_id=eq.id,
                    date=day,
                    engine_hours=engine_h,
                    idle_hours=idle_h,
                    fuel_consumed=fuel,
                    operating_days=1.0,
                )
                db.add(log)

        # ── Asset events history ──
        # Initial checkout event
        if ed["status"] not in ("available", "unassigned"):
            checkout_date = now - timedelta(days=random.randint(45, 55))
            db.add(AssetEvent(
                equipment_id=eq.id,
                event_type="checkout",
                timestamp=checkout_date,
                site_id=site_id,
                operator_id=operator_id,
                metadata={"notes": f"Deployed to project site"},
                gps_lat=sites[ed["site_idx"]].lat if ed["site_idx"] is not None else None,
                gps_lng=sites[ed["site_idx"]].lng if ed["site_idx"] is not None else None,
            ))

            # Assign event
            db.add(AssetEvent(
                equipment_id=eq.id,
                event_type="assign",
                timestamp=checkout_date + timedelta(hours=2),
                site_id=site_id,
                operator_id=operator_id,
                metadata={"notes": "Assigned to operator"},
                gps_lat=sites[ed["site_idx"]].lat if ed["site_idx"] is not None else None,
                gps_lng=sites[ed["site_idx"]].lng if ed["site_idx"] is not None else None,
            ))

            # Some usage log events
            for i in range(5):
                db.add(AssetEvent(
                    equipment_id=eq.id,
                    event_type="usage_log",
                    timestamp=checkout_date + timedelta(days=i * 7 + 3),
                    site_id=site_id,
                    metadata={"engine_hours": round(random.uniform(40, 70), 1)},
                ))

        # Create rental record
        if ed["status"] in ("active", "overdue"):
            start = now - timedelta(days=random.randint(30, 50))
            expected_ret = start + timedelta(days=30)

            rental = Rental(
                equipment_id=eq.id,
                site_id=site_id,
                operator_id=operator_id,
                start_date=start,
                expected_return=expected_ret,
                actual_return=None,
                status="overdue" if ed["status"] == "overdue" else "active",
            )
            db.add(rental)

        elif ed["status"] == "maintenance":
            db.add(AssetEvent(
                equipment_id=eq.id,
                event_type="maintenance",
                timestamp=now - timedelta(days=3),
                metadata={"reason": "Hydraulic system repair", "estimated_days": 5},
            ))

        elif ed["status"] == "available":
            # Completed rental history
            start = now - timedelta(days=90)
            db.add(Rental(
                equipment_id=eq.id,
                site_id=sites[4].id,
                operator_id=operators[4].id,
                start_date=start,
                expected_return=start + timedelta(days=30),
                actual_return=start + timedelta(days=28),
                status="completed",
            ))
            db.add(AssetEvent(
                equipment_id=eq.id,
                event_type="checkin",
                timestamp=start + timedelta(days=28),
                metadata={"condition": "good"},
            ))

        elif ed["status"] == "unassigned":
            # EQX1007 — the demo target: received but never assigned
            db.add(AssetEvent(
                equipment_id=eq.id,
                event_type="received",
                timestamp=now - timedelta(days=14),
                metadata={"notes": "New equipment received, awaiting assignment"},
            ))

    # ── Generate alerts ────────────────────────────────
    alerts_data = [
        (1, "high_idle", "high", "EQX1002 has excessive idle time — 62% idle ratio over the past 7 days"),
        (2, "overdue", "critical", "EQX1003 is 5 days past expected return date at Bangalore IT Park"),
        (3, "low_utilization", "medium", "EQX1005 utilization is at 28% — significantly below fleet average"),
        (4, "maintenance_due", "high", "EQX1004 hydraulic system repair in progress — estimated 2 more days"),
        (6, "unassigned", "medium", "EQX1007 has been unassigned for 14 days — generating zero revenue"),
    ]

    for eq_idx, alert_type, severity, message in alerts_data:
        eq = equipments[eq_idx][0]
        db.add(Alert(
            equipment_id=eq.id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            created_at=now - timedelta(hours=random.randint(1, 48)),
        ))

    # ── Generate recommendations ───────────────────────
    recs_data = [
        (6, 0, "reallocate",
         "EQX1007 is idle and unassigned. Mumbai Metro site has high demand for excavators. Reallocating would add ₹62,400/week in utilization value.",
         35.0),
        (4, 3, "reallocate",
         "EQX1005 is under-utilized at Chennai Port (28%). Hyderabad Ring Road needs excavators. Projected utilization improvement: +42%.",
         42.0),
        (1, None, "schedule_maintenance",
         "EQX1002 idle ratio is 62%, indicating potential mechanical issues. Recommend preventive maintenance check.",
         18.0),
    ]

    for eq_idx, site_idx, action, reason, improvement in recs_data:
        eq = equipments[eq_idx][0]
        target_site_id = sites[site_idx].id if site_idx is not None else None
        db.add(Recommendation(
            equipment_id=eq.id,
            target_site_id=target_site_id,
            action=action,
            reason=reason,
            projected_improvement=improvement,
        ))

    await db.commit()
    print("[OK] Database seeded with 7 assets, 5 sites, 5 operators, and 60 days of history")
