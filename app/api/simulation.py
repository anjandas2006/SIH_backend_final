import uuid
from datetime import datetime
import random
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.models import Bus, Incident, Alert
from app.schemas.schemas import SimulationState, SimulationControl
from app.services.simulation_engine import simulation_engine
from app.services.clustering_service import DefectClusteringService
from app.websocket.connection_manager import ws_manager

router = APIRouter(prefix="/simulation", tags=["Simulation Control"])

@router.get("/state", response_model=SimulationState)
def get_simulation_state(db: Session = Depends(get_db)):
    active_buses = db.query(Bus).filter(Bus.status == "ACTIVE").count()
    return {
        "is_running": simulation_engine.is_running,
        "speed_multiplier": simulation_engine.speed_multiplier,
        "active_buses": active_buses,
        "events_emitted_total": simulation_engine.step_counter * 2,
        "last_update": datetime.utcnow()
    }

@router.post("/control")
async def control_simulation(payload: SimulationControl, db: Session = Depends(get_db)):
    if payload.action == "start":
        simulation_engine.start()
    elif payload.action == "pause":
        simulation_engine.pause()
    elif payload.action == "set_speed" and payload.speed_multiplier:
        simulation_engine.set_speed(payload.speed_multiplier)
    elif payload.action == "trigger_defect":
        # Manually trigger a pothole detection from BUS-024 to demonstrate live clustering
        bus = db.query(Bus).filter(Bus.bus_number == "BUS-024").first() or db.query(Bus).first()
        cluster, is_new, defect = DefectClusteringService.cluster_defect_detection(
            db=db,
            bus_id=bus.bus_number,
            defect_type=payload.defect_type or "POTHOLE",
            latitude=bus.current_lat,
            longitude=bus.current_lng,
            confidence=0.96,
            severity="CRITICAL",
            address_description=f"Triggered Demo Defect on {bus.route.name if bus.route else 'Urban Corridor'}",
            evidence_image="/evidence/sample_pothole.jpg"
        )
        await ws_manager.broadcast_event({
            "type": "AI_DETECTION",
            "category": payload.defect_type or "POTHOLE",
            "bus_number": bus.bus_number,
            "cluster_code": cluster.cluster_code,
            "confirmed_buses": cluster.confirmed_buses_count,
            "total_detections": cluster.total_detections,
            "severity": cluster.severity,
            "lat": cluster.latitude,
            "lng": cluster.longitude,
            "timestamp": datetime.utcnow().isoformat()
        })
        return {"message": "Defect detection emitted", "cluster_code": cluster.cluster_code, "is_new": is_new}

    elif payload.action == "trigger_incident":
        bus = db.query(Bus).filter(Bus.bus_number == "BUS-024").first() or db.query(Bus).first()
        unique_suffix = uuid.uuid4().hex[:6].upper()
        inc_code = f"INC-2026-{unique_suffix}"
        inc = Incident(
            incident_code=inc_code,
            incident_type="HIT_AND_RUN",
            severity="CRITICAL",
            bus_id=bus.bus_number,
            vehicle_track_id="TRK-9901",
            detected_plate="WB12AB1234",
            plate_confidence=0.93,
            tracking_confidence=0.91,
            latitude=bus.current_lat,
            longitude=bus.current_lng,
            location_name=f"Near {bus.route.name if bus.route else 'Esplanade'}",
            status="NEW",
            evidence_image="/evidence/sample_hit_and_run.jpg",
            notes="Live triggered demonstration incident: Vehicle hit stationary curb and escaped."
        )
        db.add(inc)

        # Trigger corresponding alert
        alert = Alert(
            alert_code=f"ALT-{unique_suffix}",
            alert_type="HIT_AND_RUN",
            severity="CRITICAL",
            title=f"Critical Incident ({inc_code})",
            message=f"Hit-and-Run detected by {bus.bus_number}. Plate WB12AB1234 flagged.",
            bus_id=bus.bus_number,
            latitude=bus.current_lat,
            longitude=bus.current_lng,
            timestamp=datetime.utcnow()
        )
        db.add(alert)
        db.commit()

        await ws_manager.broadcast_alert({
            "type": "NEW_ALERT",
            "severity": "CRITICAL",
            "title": alert.title,
            "message": alert.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        return {"message": "Incident and alert created", "incident_code": inc_code}

    return get_simulation_state(db)
