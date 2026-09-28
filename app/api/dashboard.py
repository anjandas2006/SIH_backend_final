from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Bus, RoadDefectCluster, TrafficEvent, Incident, Alert, Detection
from app.schemas.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    total_buses = db.query(Bus).count()
    active_buses = db.query(Bus).filter(Bus.status == "ACTIVE").count()
    maintenance_buses = db.query(Bus).filter(Bus.status == "MAINTENANCE").count()
    inactive_buses = db.query(Bus).filter(Bus.status == "INACTIVE").count()

    # Sum of events today from active buses
    buses = db.query(Bus).all()
    ai_events_today = sum(b.events_today_count for b in buses) + 1240

    potholes_count = db.query(RoadDefectCluster).filter(RoadDefectCluster.defect_type == "POTHOLE").count()
    traffic_hotspots = db.query(TrafficEvent).filter(TrafficEvent.density_level.in_(["HIGH", "SEVERE"])).count()
    active_incidents = db.query(Incident).filter(Incident.status.in_(["NEW", "UNDER_REVIEW", "VERIFIED"])).count()
    waterlogging_count = db.query(RoadDefectCluster).filter(RoadDefectCluster.defect_type == "WATERLOGGING").count()
    unresolved_defects = db.query(RoadDefectCluster).filter(RoadDefectCluster.status == "UNRESOLVED").count()

    # Formatted recent AI events ticker
    recent_events = []

    # Recent defect clusters
    clusters = db.query(RoadDefectCluster).order_by(RoadDefectCluster.last_detected_at.desc()).limit(4).all()
    for c in clusters:
        recent_events.append({
            "id": c.id,
            "type": "DEFECT",
            "title": f"{c.defect_type.replace('_', ' ')} Detected",
            "bus": f"Confirmed by {c.confirmed_buses_count} buses",
            "location": c.address_description or "Urban Corridor",
            "time": c.last_detected_at.strftime("%I:%M %p"),
            "confidence": f"{int(c.confidence * 100)}%",
            "severity": c.severity,
            "cluster_code": c.cluster_code,
            "evidence": c.evidence_image
        })

    # Recent traffic events
    traffic_events = db.query(TrafficEvent).order_by(TrafficEvent.timestamp.desc()).limit(3).all()
    for t in traffic_events:
        recent_events.append({
            "id": t.id,
            "type": "TRAFFIC",
            "title": f"Traffic Congestion ({t.density_percent}%)",
            "bus": t.bus_id,
            "location": t.location_name,
            "time": t.timestamp.strftime("%I:%M %p"),
            "confidence": "96%",
            "severity": t.density_level,
            "cluster_code": "TRAFFIC",
            "evidence": "/evidence/sample_damaged_road.jpg"
        })

    # Recent incidents
    incidents = db.query(Incident).order_by(Incident.timestamp.desc()).limit(2).all()
    for inc in incidents:
        recent_events.append({
            "id": inc.id,
            "type": "INCIDENT",
            "title": f"{inc.incident_type.replace('_', ' ')}",
            "bus": inc.bus_id,
            "location": inc.location_name,
            "time": inc.timestamp.strftime("%I:%M %p"),
            "confidence": f"{int(inc.tracking_confidence * 100)}%",
            "severity": inc.severity,
            "cluster_code": inc.incident_code,
            "evidence": inc.evidence_image
        })

    # Hourly traffic volume data for chart
    hourly_trend = [
        {"hour": "06:00", "vehicles": 420, "speed": 42.5, "density": 35},
        {"hour": "07:00", "vehicles": 890, "speed": 34.0, "density": 58},
        {"hour": "08:00", "vehicles": 1450, "speed": 22.1, "density": 78},
        {"hour": "09:00", "vehicles": 1820, "speed": 16.4, "density": 88},
        {"hour": "10:00", "vehicles": 1650, "speed": 19.8, "density": 82},
        {"hour": "11:00", "vehicles": 1320, "speed": 25.0, "density": 65},
        {"hour": "12:00", "vehicles": 1180, "speed": 28.4, "density": 55},
        {"hour": "13:00", "vehicles": 1050, "speed": 31.2, "density": 48}
    ]

    traffic_metrics = {
        "overall_density": 76,
        "overall_status": "HIGH",
        "avg_speed": 22.4,
        "hourly_trend": hourly_trend
    }

    road_health_metrics = {
        "healthy_percentage": 78,
        "damaged_percentage": 22,
        "unresolved": unresolved_defects,
        "under_review": db.query(RoadDefectCluster).filter(RoadDefectCluster.status == "UNDER_REVIEW").count(),
        "work_order_issued": db.query(RoadDefectCluster).filter(RoadDefectCluster.status == "WORK_ORDER_ISSUED").count(),
        "repaired": db.query(RoadDefectCluster).filter(RoadDefectCluster.status == "REPAIRED").count(),
        "rm_pci_index": 7.4,
        "pci_rating_label": "Level 2 (Good / Minor Wear)",
        "level_1_excellent_pct": 42,
        "level_2_good_pct": 26,
        "level_3_fair_pct": 15,
        "level_4_poor_pct": 11,
        "level_5_critical_pct": 6,
        "surveyed_network_km": 168.4,
        "capture_interval": "Every 10 feet with GPS"
    }

    incident_summary = {
        "new": db.query(Incident).filter(Incident.status == "NEW").count(),
        "under_review": db.query(Incident).filter(Incident.status == "UNDER_REVIEW").count(),
        "verified": db.query(Incident).filter(Incident.status == "VERIFIED").count(),
        "resolved": db.query(Incident).filter(Incident.status == "RESOLVED").count()
    }

    fleet_status = {
        "active": active_buses,
        "maintenance": maintenance_buses,
        "inactive": inactive_buses
    }

    return {
        "active_buses": active_buses,
        "total_buses": total_buses,
        "ai_events_today": ai_events_today,
        "potholes_detected": potholes_count,
        "traffic_hotspots": traffic_hotspots,
        "active_incidents": active_incidents,
        "waterlogging_points": waterlogging_count,
        "unresolved_defects": unresolved_defects,
        "recent_events": recent_events,
        "traffic_metrics": traffic_metrics,
        "road_health_metrics": road_health_metrics,
        "incident_summary": incident_summary,
        "fleet_status": fleet_status
    }
