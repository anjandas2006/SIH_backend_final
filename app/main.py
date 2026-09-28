import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.api import (
    auth, dashboard, buses, routes, defects, traffic,
    incidents, alerts, video, analytics, reports, settings as sys_settings, simulation, roadmetrics
)
from app.websocket.connection_manager import ws_manager
from app.services.simulation_engine import simulation_engine
from app.services.evidence_service import EvidenceService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables, stock evidence, and start simulation loop
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("[Startup warning - db tables]:", e)

    try:
        EvidenceService.create_stock_evidence()
    except Exception as e:
        print("[Startup warning - stock evidence]:", e)

    if not os.getenv("VERCEL"):
        try:
            simulation_engine.start()
            print("[BusSense AI] Backend initialized. Simulation engine running.")
        except Exception as e:
            print("[Startup warning - simulation engine]:", e)
    else:
        print("[BusSense AI] Backend initialized in Vercel Serverless mode.")

    yield

    # Shutdown
    if not os.getenv("VERCEL"):
        try:
            simulation_engine.pause()
            print("[BusSense AI] Shutting down simulation engine.")
        except Exception:
            pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-Powered Mobile Urban Intelligence Platform Using Public Transport Fleet",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files for Evidence Images
app.mount("/evidence", StaticFiles(directory=settings.EVIDENCE_DIR), name="evidence")

# Vercel Serverless Path Normalization Middleware
@app.middleware("http")
async def vercel_path_middleware(request, call_next):
    query_str = request.scope.get("query_string", b"").decode("utf-8", errors="ignore")
    if "__path=" in query_str:
        import urllib.parse
        parsed_qs = urllib.parse.parse_qs(query_str)
        if "__path" in parsed_qs and parsed_qs["__path"]:
            raw_target = parsed_qs.pop("__path")[0]
            if "?" in raw_target:
                p_part, q_part = raw_target.split("?", 1)
            else:
                p_part, q_part = raw_target, ""

            while p_part.startswith("//"):
                p_part = p_part[1:]
            if not p_part.startswith("/"):
                p_part = "/" + p_part

            request.scope["path"] = p_part

            reconstructed_q = []
            if q_part:
                reconstructed_q.append(q_part)
            for k, vals in parsed_qs.items():
                for v in vals:
                    reconstructed_q.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
            request.scope["query_string"] = "&".join(reconstructed_q).encode("utf-8")

    path = request.scope.get("path", "")
    if path in ["/api/index.py", "/api/index"]:
        request.scope["path"] = "/"
    elif path == "/api/docs":
        request.scope["path"] = "/docs"
    elif path == "/api/openapi.json":
        request.scope["path"] = "/openapi.json"
    return await call_next(request)



# Include Routers (Both with /api prefix and without, for maximum compatibility with serverless rewrites)
ALL_ROUTERS = [
    auth.router, dashboard.router, buses.router, routes.router, defects.router,
    traffic.router, incidents.router, alerts.router, video.router,
    analytics.router, reports.router, sys_settings.router, simulation.router,
    roadmetrics.router
]

for r in ALL_ROUTERS:
    app.include_router(r, prefix=settings.API_V1_PREFIX)
    app.include_router(r)


# WebSocket Endpoints
@app.websocket("/ws/fleet")
async def websocket_fleet_endpoint(websocket: WebSocket):
    await ws_manager.connect_fleet(websocket)
    try:
        while True:
            # Keep-alive receive ping
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_fleet(websocket)

@app.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    await ws_manager.connect_events(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_events(websocket)

@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    await ws_manager.connect_alerts(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_alerts(websocket)

from fastapi import Request

@app.get("/")
@app.get("/api")
@app.get("/api/")
@app.get("/api/index.py")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "demo_mode": settings.DEMO_MODE,
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
