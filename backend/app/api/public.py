from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DwdAgriAkpDensityDaily, DwdAgriAttendanceDaily, DwdAgriHarvestDaily

router = APIRouter(tags=["public"])


def _f(v: Optional[float]) -> float:
    return v or 0.0


@router.get("/public/leader")
def leader_dashboard(db: Session = Depends(get_db)) -> dict:
    today = date.today()
    since = today - timedelta(days=30)

    # ── Production ────────────────────────────────────────────
    harvest_rows = list(db.scalars(
        select(DwdAgriHarvestDaily)
        .where(DwdAgriHarvestDaily.report_date >= since)
        .order_by(DwdAgriHarvestDaily.report_date)
    ).all())

    latest_prod_date: Optional[date] = db.scalar(
        select(func.max(DwdAgriHarvestDaily.report_date))
    )

    prod_by_date: dict[date, float] = defaultdict(float)
    for r in harvest_rows:
        prod_by_date[r.report_date] += _f(r.actual_kg)
    production_trend = [
        {"date": str(d), "ton": round(kg / 1000, 2)}
        for d, kg in sorted(prod_by_date.items())
    ]

    today_production_ton = 0.0
    mtd_production_ton = 0.0
    production_by_site: list[dict] = []
    if latest_prod_date:
        latest_rows = [r for r in harvest_rows if r.report_date == latest_prod_date]
        site_map: dict[str, dict] = defaultdict(lambda: {"today_kg": 0.0, "mtd_kg": 0.0})
        for r in latest_rows:
            site_map[r.site]["today_kg"] += _f(r.actual_kg)
            site_map[r.site]["mtd_kg"] += _f(r.mtd_actual_kg)
        today_production_ton = sum(v["today_kg"] for v in site_map.values()) / 1000
        mtd_production_ton = sum(v["mtd_kg"] for v in site_map.values()) / 1000
        production_by_site = [
            {
                "site": site,
                "today_ton": round(v["today_kg"] / 1000, 2),
                "mtd_ton": round(v["mtd_kg"] / 1000, 2),
            }
            for site, v in sorted(site_map.items())
        ]

    # ── Attendance ────────────────────────────────────────────
    att_rows = list(db.scalars(
        select(DwdAgriAttendanceDaily)
        .where(DwdAgriAttendanceDaily.report_date >= since)
        .order_by(DwdAgriAttendanceDaily.report_date)
    ).all())

    latest_att_date: Optional[date] = db.scalar(
        select(func.max(DwdAgriAttendanceDaily.report_date))
    )

    att_present: dict[date, float] = defaultdict(float)
    att_total: dict[date, float] = defaultdict(float)
    for r in att_rows:
        att_present[r.report_date] += _f(r.total_present)
        att_total[r.report_date] += _f(r.own_total) + _f(r.contractor_total)

    attendance_trend = [
        {
            "date": str(d),
            "rate": round(att_present[d] / att_total[d] * 100, 1) if att_total[d] > 0 else None,
        }
        for d in sorted(att_present.keys())
    ]

    today_attendance_rate: Optional[float] = None
    attendance_by_site: list[dict] = []
    if latest_att_date:
        latest_att = [r for r in att_rows if r.report_date == latest_att_date]
        site_att: dict[str, dict] = defaultdict(lambda: {"present": 0.0, "total": 0.0})
        for r in latest_att:
            site_att[r.site]["present"] += _f(r.total_present)
            site_att[r.site]["total"] += _f(r.own_total) + _f(r.contractor_total)
        total_p = sum(v["present"] for v in site_att.values())
        total_t = sum(v["total"] for v in site_att.values())
        today_attendance_rate = round(total_p / total_t * 100, 1) if total_t > 0 else None
        attendance_by_site = [
            {
                "site": site,
                "rate": round(v["present"] / v["total"] * 100, 1) if v["total"] > 0 else None,
                "present": int(v["present"]),
                "total": int(v["total"]),
            }
            for site, v in sorted(site_att.items())
        ]

    # ── AKP ──────────────────────────────────────────────────
    latest_akp_date: Optional[date] = db.scalar(
        select(func.max(DwdAgriAkpDensityDaily.report_date))
    )
    akp_by_division: list[dict] = []
    if latest_akp_date:
        akp_rows = list(db.scalars(
            select(DwdAgriAkpDensityDaily)
            .where(DwdAgriAkpDensityDaily.report_date == latest_akp_date)
        ).all())
        div_map: dict[str, list[float]] = defaultdict(list)
        for r in akp_rows:
            if r.akp_percent is not None:
                div_map[r.division].append(r.akp_percent)
        akp_by_division = [
            {"division": div, "akp": round(sum(vals) / len(vals), 1)}
            for div, vals in sorted(div_map.items())
            if vals
        ]

    return {
        "data_date": str(latest_prod_date) if latest_prod_date else None,
        "att_data_date": str(latest_att_date) if latest_att_date else None,
        "kpis": {
            "today_production_ton": round(today_production_ton, 2),
            "mtd_production_ton": round(mtd_production_ton, 2),
            "today_attendance_rate": today_attendance_rate,
        },
        "production_trend": production_trend,
        "production_by_site": production_by_site,
        "attendance_trend": attendance_trend,
        "attendance_by_site": attendance_by_site,
        "akp_by_division": akp_by_division,
    }
