from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DwdAgriAkpDensityDaily, DwdAgriAttendanceDaily, DwdAgriHarvestDaily

router = APIRouter(tags=["entry"])


def _upsert(db: Session, model_class: Any, index_elements: list[str], **values: Any) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(model_class).values(**values)
    update_cols = {k: stmt.excluded[k] for k in values if k not in index_elements}
    stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)
    db.execute(stmt)


# ─── 铲果日产量 ────────────────────────────────────────────────────────────────

class HarvestRow(BaseModel):
    division: str
    mature_area_ha: Optional[float] = None
    actual_kg: Optional[float] = None
    mtd_actual_kg: Optional[float] = None


class HarvestEntry(BaseModel):
    report_date: date
    site: str
    rows: list[HarvestRow]


@router.post("/entry/harvest")
def submit_harvest(payload: HarvestEntry, db: Session = Depends(get_db)) -> dict[str, str]:
    saved = 0
    for row in payload.rows:
        if not row.division.strip():
            continue
        _upsert(
            db, DwdAgriHarvestDaily,
            ["report_date", "site", "division"],
            report_date=payload.report_date,
            site=payload.site,
            division=row.division.strip(),
            batch_no="manual",
            mature_area_ha=row.mature_area_ha,
            actual_kg=row.actual_kg,
            mtd_actual_kg=row.mtd_actual_kg,
            quality_status="ok",
        )
        saved += 1
    db.commit()
    return {"message": f"已保存 {saved} 行铲果产量数据"}


# ─── AKP 铲果密度 ──────────────────────────────────────────────────────────────

class AkpRow(BaseModel):
    division: str
    blok: str = ""
    sap: str = ""
    luas_ha: Optional[float] = None
    tt_year: Optional[int] = None
    panen_count: Optional[float] = None
    akp_percent: Optional[float] = None
    panen_kg: Optional[float] = None
    jumlah_janjang: Optional[float] = None
    tk_panen: Optional[float] = None
    keterangan: str = ""


class AkpEntry(BaseModel):
    report_date: date
    site: str
    rows: list[AkpRow]


@router.post("/entry/akp-density")
def submit_akp(payload: AkpEntry, db: Session = Depends(get_db)) -> dict[str, str]:
    saved = 0
    for row in payload.rows:
        if not row.division.strip():
            continue
        _upsert(
            db, DwdAgriAkpDensityDaily,
            ["report_date", "site", "division", "blok"],
            report_date=payload.report_date,
            site=payload.site,
            division=row.division.strip(),
            blok=row.blok.strip(),
            batch_no="manual",
            sap=row.sap,
            luas_ha=row.luas_ha,
            tt_year=row.tt_year,
            panen_count=row.panen_count,
            akp_percent=row.akp_percent,
            panen_kg=row.panen_kg,
            jumlah_janjang=row.jumlah_janjang,
            tk_panen=row.tk_panen,
            keterangan=row.keterangan,
            quality_status="ok",
        )
        saved += 1
    db.commit()
    return {"message": f"已保存 {saved} 行 AKP 密度数据"}


# ─── 出勤 ──────────────────────────────────────────────────────────────────────

class AttendanceRow(BaseModel):
    division: str
    worker_type: str
    managed_area_ha: Optional[float] = None
    required_count: Optional[float] = None
    own_total: Optional[float] = None
    contractor_total: Optional[float] = None
    own_present: Optional[float] = None
    contractor_present: Optional[float] = None
    total_present: Optional[float] = None
    leave_count: Optional[float] = None
    annual_leave_count: Optional[float] = None
    sick_count: Optional[float] = None
    absent_count: Optional[float] = None


class AttendanceEntry(BaseModel):
    report_date: date
    site: str
    rows: list[AttendanceRow]


@router.post("/entry/attendance")
def submit_attendance(payload: AttendanceEntry, db: Session = Depends(get_db)) -> dict[str, str]:
    saved = 0
    for row in payload.rows:
        if not row.worker_type.strip():
            continue
        _upsert(
            db, DwdAgriAttendanceDaily,
            ["report_date", "site", "division", "worker_type"],
            report_date=payload.report_date,
            site=payload.site,
            division=row.division.strip(),
            worker_type=row.worker_type.strip(),
            batch_no="manual",
            managed_area_ha=row.managed_area_ha,
            required_count=row.required_count,
            own_total=row.own_total,
            contractor_total=row.contractor_total,
            own_present=row.own_present,
            contractor_present=row.contractor_present,
            total_present=row.total_present,
            leave_count=row.leave_count,
            annual_leave_count=row.annual_leave_count,
            sick_count=row.sick_count,
            absent_count=row.absent_count,
            quality_status="ok",
        )
        saved += 1
    db.commit()
    return {"message": f"已保存 {saved} 行出勤数据"}
