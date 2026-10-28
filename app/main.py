import os
import hmac
import hashlib
from fastapi import FastAPI, Depends, Query, Header, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from app.ingestion import DataEngine
from app.auth import verify_abdm_credentials

app = FastAPI(
    title="E-Sanjivani ABDM-UP Internal Monitoring Service",
    description="Authorized internal monitoring system for ABDM Uttar Pradesh State Directorate",
    version="1.1.0"
)

UP_CSV = os.getenv("UP_CSV_PATH", "data/E-Sanjeevani_Daily_Reporting_UP_Status.csv")
DIST_CSV = os.getenv("DIST_CSV_PATH", "data/E-Sanjeevani_Daily_Reporting_District_Wise_Status.csv")
SYNC_SECRET = os.getenv("SYNC_WEBHOOK_SECRET", "ABDM_UP_HOT_RELOAD_TOKEN_2026")

# In-memory single instance of data engine
engine = DataEngine(UP_CSV, DIST_CSV)

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "esanjivani-abdmup-dashboard",
        "state": "UP",
        "latest_reporting_date": engine.get_available_dates()[0] if engine.get_available_dates() else None,
        "total_records_state": len(engine.df_up),
        "total_records_district": len(engine.df_dist)
    }

@app.post("/api/v1/internal/reload-data")
def hot_reload_cache(x_sync_token: str = Header(None, alias="X-Sync-Token")):
    """
    Internal Webhook Endpoint
    Triggered automatically by scripts/sync_drive.py after syncing files.
    Reloads both UP and District data frames into memory with zero downtime.
    """
    if not x_sync_token or not hmac.compare_digest(x_sync_token, SYNC_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing sync authorization token."
        )

    try:
        engine.load_and_clean()
        latest_date = engine.get_available_dates()[0] if engine.get_available_dates() else "N/A"
        return {
            "status": "SUCCESS",
            "message": "In-memory datasets reloaded successfully.",
            "latest_date": latest_date,
            "total_state_rows": len(engine.df_up),
            "total_district_rows": len(engine.df_dist)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data reload failed: {str(e)}"
        )

@app.get("/api/v1/dates", dependencies=[Depends(verify_abdm_credentials)])
def list_dates():
    return {"dates": engine.get_available_dates()}

@app.get("/api/v1/kpi/summary", dependencies=[Depends(verify_abdm_credentials)])
def get_kpis(date: str = Query("2026-10-27")):
    res = engine.get_summary_kpis(date)
    if not res:
        return JSONResponse(status_code=404, content={"message": f"No data found for date {date}"})
    return res

@app.get("/api/v1/districts/performance", dependencies=[Depends(verify_abdm_credentials)])
def get_districts(date: str = Query("2026-10-27")):
    data = engine.get_district_performance(date)
    return {"date": date, "total_reporting": len(data), "districts": data}

@app.get("/api/v1/export/report-image", dependencies=[Depends(verify_abdm_credentials)])
def get_report_image():
    png_path = "reports/esanjivani_abdmup_daily_summary_light_20261027.png"
    if os.path.exists(png_path):
        return FileResponse(png_path, media_type="image/png", filename="ABDM_UP_eSanjeevani_Summary_Light_20261027.png")
    return JSONResponse(status_code=404, content={"message": "Report image not generated"})
