from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
import logging
from .database import get_db, engine
from .models import Base, RiskConfig, RiskConfigUpdate, AppStatus, SymbolRisk, SymbolRiskUpdate
from .config import config
from .kite_session import kite_mgr
from .position_manager import pos_mgr
from .risk_monitor import risk_monitor
from .squareoff_engine import square_off_all_fo
from .telegram_notifier import telegram
from .ticker_manager import ticker_mgr

# Initialize Database
Base.metadata.create_all(bind=engine)

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="F&O Risk Management System")

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Risk Config in DB if not exists
@app.on_event("startup")
async def startup_event():
    db = next(get_db())
    if not db.query(RiskConfig).first():
        new_config = RiskConfig(
            max_loss=config.MAX_LOSS_DEFAULT,
            profit_target=config.PROFIT_TARGET_DEFAULT,
            auto_squareoff=config.AUTO_SQUAREOFF_ENABLED,
            check_interval=config.CHECK_INTERVAL_SECONDS,
            trailing_sl_enabled=False,
            trail_distance=0.0,
            peak_pnl=0.0,
            auto_exit_time="15:15"
        )
        db.add(new_config)

    if not db.query(AppStatus).first():
        db.add(AppStatus(status="ACTIVE"))

    db.commit()
    db.close()

    # Try to load existing session
    session_status = kite_mgr.load_session()
    if session_status == "ACTIVE":
        logger.info("Session restored successfully")
        ticker_mgr.start(kite_mgr.access_token)
        # Start risk monitor loop
        asyncio.create_task(risk_monitor.check_risk_loop())
        await telegram.send(f"🟢 <b>RMS Active</b>\nNFO + BFO | Options + Futures | Max Loss: ₹{config.MAX_LOSS_DEFAULT} | Target: ₹{config.PROFIT_TARGET_DEFAULT}")
    else:
        logger.warning(f"Kite session not active: {session_status}")
        if session_status == "TOKEN_EXPIRED":
            await telegram.send("🔐 <b>LOGIN REQUIRED</b>\nKite token expired.")

@app.get("/auth/login")
def login():
    return {"login_url": kite_mgr.get_login_url()}

@app.get("/auth/callback")
async def callback(request_token: str):
    success = kite_mgr.set_access_token(request_token)
    if success:
        ticker_mgr.start(kite_mgr.access_token)
        if not risk_monitor.is_running:
            asyncio.create_task(risk_monitor.check_risk_loop())

        db = next(get_db())
        conf = db.query(RiskConfig).first()
        db.close()

        await telegram.send(f"🟢 <b>RMS Active (Session Started)</b>\nMax Loss: ₹{conf.max_loss} | Target: ₹{conf.profit_target}")
        return RedirectResponse(url="/")
    else:
        raise HTTPException(status_code=400, detail="Failed to generate session")

@app.get("/auth/status")
def get_auth_status():
    status = kite_mgr.load_session()
    return {"status": status}

@app.get("/positions/fo")
async def get_fo_positions():
    await pos_mgr.fetch_and_filter_positions()
    return pos_mgr.get_all_positions_list()

@app.get("/pnl/summary")
def get_pnl_summary():
    return pos_mgr.get_pnl_breakdown()

@app.get("/config")
def get_risk_config(db: Session = Depends(get_db)):
    return db.query(RiskConfig).first()

@app.put("/config")
def update_risk_config(conf_update: RiskConfigUpdate, db: Session = Depends(get_db)):
    conf = db.query(RiskConfig).first()
    conf.max_loss = conf_update.max_loss
    conf.profit_target = conf_update.profit_target
    conf.auto_squareoff = conf_update.auto_squareoff
    conf.check_interval = conf_update.check_interval
    conf.trailing_sl_enabled = conf_update.trailing_sl_enabled
    conf.trail_distance = conf_update.trail_distance
    conf.auto_exit_time = conf_update.auto_exit_time

    # Reset peak_pnl when config is updated manually
    if conf.trailing_sl_enabled:
        breakdown = pos_mgr.get_pnl_breakdown()
        current_pnl = breakdown["total_pnl"]
        conf.peak_pnl = max(conf.peak_pnl, current_pnl)

        # Update max_loss immediately based on current peak
        new_max_loss = conf.peak_pnl - conf.trail_distance
        if new_max_loss > conf.max_loss:
            conf.max_loss = new_max_loss
            logger.info(f"Trailing SL Updated: New Max Loss set to {conf.max_loss}")

    db.commit()
    return conf

@app.post("/squareoff/all")
async def manual_squareoff():
    results = await square_off_all_fo()
    await telegram.send(f"🔴 <b>MANUAL SQUARE-OFF TRIGGERED</b>\nProcessed {len(results)} positions.")
    return results

@app.get("/status")
async def get_app_status_api():
    status = await risk_monitor.get_app_status()
    return {"status": status}

@app.get("/config/symbols")
def get_all_symbol_risks(db: Session = Depends(get_db)):
    return db.query(SymbolRisk).all()

@app.post("/config/symbols")
def update_symbol_risk(risk_update: SymbolRiskUpdate, db: Session = Depends(get_db)):
    risk = db.query(SymbolRisk).filter(SymbolRisk.tradingsymbol == risk_update.tradingsymbol).first()
    if not risk:
        risk = SymbolRisk(tradingsymbol=risk_update.tradingsymbol)
        db.add(risk)

    risk.stop_loss = risk_update.stop_loss
    risk.target = risk_update.target
    db.commit()
    return risk

@app.post("/status/resume")
async def resume_monitoring():
    await risk_monitor.set_app_status("ACTIVE")
    return {"status": "ACTIVE"}

@app.post("/status/pause")
async def pause_monitoring():
    await risk_monitor.set_app_status("HALTED")
    return {"status": "HALTED"}

@app.post("/telegram/test")
async def test_telegram():
    await telegram.send("🧪 <b>Test Message</b> from RMS Backend")
    return {"status": "sent"}

@app.websocket("/ws/pnl")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            breakdown = pos_mgr.get_pnl_breakdown()
            status = await risk_monitor.get_app_status()

            db = next(get_db())
            conf = db.query(RiskConfig).first()
            symbol_risks = db.query(SymbolRisk).all()
            symbol_risks_dict = {r.tradingsymbol: {"sl": r.stop_loss, "target": r.target} for r in symbol_risks}
            db.close()

            await websocket.send_json({
                "pnl": breakdown,
                "status": status,
                "positions": pos_mgr.get_all_positions_list(),
                "config": {
                    "max_loss": conf.max_loss,
                    "profit_target": conf.profit_target,
                    "trailing_sl_enabled": conf.trailing_sl_enabled,
                    "trail_distance": conf.trail_distance,
                    "auto_exit_time": conf.auto_exit_time
                },
                "symbol_risks": symbol_risks_dict
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
