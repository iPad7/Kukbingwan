import os
import pathlib
from typing import Any

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from openpyxl import Workbook

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sot:sot@localhost:5433/sot")
ARTIFACT_DIR = pathlib.Path(os.getenv("ARTIFACT_DIR", "./artifacts"))
SAMPLE_XLSX = ARTIFACT_DIR / "sample_rankings.xlsx"

app = FastAPI(title="Web Viewer (Dummy)", version="0.1.0")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def ensure_sample_artifact():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    if SAMPLE_XLSX.exists():
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "rankings"
    ws.append(["dt", "platform_id", "category_id", "rank", "product_title_raw", "product_url"])
    ws.append(["2024-09-01", 1, 1, 1, "Laneige Water Bank", "https://www.amazon.com/dp/B000000001"])
    ws.append(["2024-09-01", 1, 1, 2, "Laneige Lip Sleeping Mask", "https://www.amazon.com/dp/B000000002"])
    ws.append(["2024-09-01", 2, 3, 1, "Laneige Water Bank JP", "https://www.cosme.net/product/product_id"])
    ws.append(["2024-09-01", 2, 4, 1, "Laneige Lip Mask JP", "https://www.cosme.net/product/product_id2"])
    wb.save(SAMPLE_XLSX)


@app.on_event("startup")
def bootstrap():
    ensure_sample_artifact()


@app.get("/")
def root():
    return {
        "message": "Web Viewer dummy app",
        "health": "/health",
        "platforms": "/platforms",
        "categories": "/categories?platform_id=1",
        "rankings": "/rankings?dt=2024-09-01&platform_id=1&category_id=1",
        "reports": "/reports",
        "download": "/downloads/rankings.xlsx",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/platforms")
def get_platforms():
    rows = fetch_all("SELECT platform_id, name FROM platforms ORDER BY platform_id")
    return {"items": rows}


@app.get("/categories")
def get_categories(platform_id: int | None = Query(default=None)):
    if platform_id:
        rows = fetch_all(
            "SELECT category_id, platform_id, name, source_url FROM categories WHERE platform_id = %s ORDER BY category_id",
            (platform_id,),
        )
    else:
        rows = fetch_all("SELECT category_id, platform_id, name, source_url FROM categories ORDER BY category_id")
    return {"items": rows}


@app.get("/rankings")
def get_rankings(
    dt: str = Query(..., description="Date in YYYY-MM-DD"),
    platform_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    conditions = ["dt = %s"]
    params: list[Any] = [dt]
    if platform_id:
        conditions.append("platform_id = %s")
        params.append(platform_id)
    if category_id:
        conditions.append("category_id = %s")
        params.append(category_id)
    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT dt, platform_id, category_id, rank, listing_id, product_title_raw, product_url, captured_at
        FROM ranking_daily
        WHERE {where_clause}
        ORDER BY rank ASC
        LIMIT %s
    """
    params.append(limit)
    rows = fetch_all(query, tuple(params))
    return {"items": rows}


@app.get("/downloads/rankings.xlsx")
def download_rankings():
    if not SAMPLE_XLSX.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(SAMPLE_XLSX, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="rankings.xlsx")


@app.get("/reports")
def list_reports(limit: int = Query(default=20, ge=1, le=100)):
    rows = fetch_all(
        """
        SELECT report_id, period_start, period_end, platform_scope, category_scope, notion_url, summary, created_at
        FROM reports
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return {"items": rows}


@app.exception_handler(Exception)
def handle_exception(request, exc):  # type: ignore[override]
    # Minimal error surface for dummy stage.
    return JSONResponse(status_code=500, content={"detail": str(exc)})
