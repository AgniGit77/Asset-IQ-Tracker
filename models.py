"""SQLAlchemy ORM models — all tables for CAT AssetIQ."""
from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(String(20), unique=True, nullable=False, index=True)  # EQX1001
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)      # Excavator, Bulldozer, etc.
    model = Column(String(50))
    year = Column(Integer)
    serial_number = Column(String(50))
    rental_rate_per_hour = Column(Float, default=0.0)
    image_url = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    events = relationship("AssetEvent", back_populates="equipment", lazy="selectin")
    usage_logs = relationship("UsageLog", back_populates="equipment", lazy="selectin")
    rentals = relationship("Rental", back_populates="equipment", lazy="selectin")
    alerts = relationship("Alert", back_populates="equipment", lazy="selectin")
    recommendations = relationship("Recommendation", back_populates="equipment", lazy="selectin")
    inspection_reports = relationship("InspectionReport", back_populates="equipment", lazy="selectin")


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    lat = Column(Float)
    lng = Column(Float)
    demand_level = Column(String(20), default="medium")  # low, medium, high
    created_at = Column(DateTime, default=datetime.utcnow)

    rentals = relationship("Rental", back_populates="site", lazy="selectin")
    events = relationship("AssetEvent", back_populates="site", lazy="selectin")


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    license_number = Column(String(50))
    certification = Column(String(100))
    contact = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    rentals = relationship("Rental", back_populates="operator", lazy="selectin")
    events = relationship("AssetEvent", back_populates="operator", lazy="selectin")


class Rental(Base):
    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"))
    operator_id = Column(Integer, ForeignKey("operators.id"))
    start_date = Column(DateTime, nullable=False)
    expected_return = Column(DateTime)
    actual_return = Column(DateTime)
    status = Column(String(20), default="active")  # active, completed, overdue
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="rentals")
    site = relationship("Site", back_populates="rentals")
    operator = relationship("Operator", back_populates="rentals")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    engine_hours = Column(Float, default=0.0)
    idle_hours = Column(Float, default=0.0)
    fuel_consumed = Column(Float, default=0.0)  # litres
    operating_days = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="usage_logs")


class AssetEvent(Base):
    """The immutable ledger — every state change writes a row here."""
    __tablename__ = "asset_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    event_type = Column(String(30), nullable=False)  # checkout, checkin, assign, usage_log, maintenance, anomaly_flagged, reallocation
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=True)
    event_metadata = Column(JSON, default=dict)  # flexible payload per event type
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="events")
    site = relationship("Site", back_populates="events")
    operator = relationship("Operator", back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)  # overdue, low_utilization, high_idle, anomaly, maintenance_due
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    equipment = relationship("Equipment", back_populates="alerts")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    target_site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    action = Column(String(50), nullable=False)  # reallocate, schedule_maintenance, decommission
    reason = Column(Text, nullable=False)
    projected_improvement = Column(Float, default=0.0)  # percentage
    is_applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

    equipment = relationship("Equipment", back_populates="recommendations")
    target_site = relationship("Site")


class CostConfig(Base):
    __tablename__ = "cost_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_cost_per_hour = Column(Float, default=350.0)  # ₹
    fuel_cost_per_litre = Column(Float, default=95.0)       # ₹
    idle_fuel_burn_rate = Column(Float, default=4.5)         # litres/hour
    updated_at = Column(DateTime, default=datetime.utcnow)


class InspectionReport(Base):
    __tablename__ = "inspection_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=True)
    photos = Column(JSON, default=list)       # list of {zone, url, filename}
    zone_results = Column(JSON, default=list) # list of {zone, damage_type, severity, description}
    overall_score = Column(Float, default=100.0)  # 0-100
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="inspection_reports")
    rental = relationship("Rental")
