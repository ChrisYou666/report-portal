from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret, encrypt_secret
from app.db import get_db
from app.models import DataSourceConfig, DimBlok, DimCompany, DimDivision, DimFactory, DimSite

router = APIRouter(tags=["master"])


# ─── Pydantic schemas ──────────────────────────────────────────────────────────

class CompanyOut(BaseModel):
    id: int; code: str; name: str; name_id: str; country: str
    is_active: bool; source: str; external_id: str; remark: str
    class Config: from_attributes = True

class CompanyIn(BaseModel):
    code: str; name: str; name_id: str = ""; country: str = "Indonesia"
    is_active: bool = True; external_id: str = ""; remark: str = ""

class FactoryOut(BaseModel):
    id: int; company_code: str; code: str; name: str; name_id: str
    factory_type: str; location: str; capacity_ton_per_hour: Optional[float]
    is_active: bool; source: str; external_id: str; remark: str
    class Config: from_attributes = True

class FactoryIn(BaseModel):
    company_code: str; code: str; name: str; name_id: str = ""
    factory_type: str = "pom"; location: str = ""
    capacity_ton_per_hour: Optional[float] = None
    is_active: bool = True; external_id: str = ""; remark: str = ""

class BlokOut(BaseModel):
    id: int; company_code: str; site_code: str; division_code: str; code: str; name: str
    luas_ha: Optional[float]; planting_year: Optional[int]; maturity_stage: str
    palm_count: Optional[int]; sph: Optional[float]
    is_active: bool; source: str; external_id: str; remark: str
    class Config: from_attributes = True

class BlokIn(BaseModel):
    company_code: str = ""; site_code: str; division_code: str; code: str; name: str = ""
    luas_ha: Optional[float] = None; planting_year: Optional[int] = None
    maturity_stage: str = "TM"; palm_count: Optional[int] = None; sph: Optional[float] = None
    is_active: bool = True; external_id: str = ""; remark: str = ""

class SiteOut(BaseModel):
    id: int; company_code: str; code: str; name: str; name_id: str; region: str
    country: str; is_active: bool; source: str; external_id: str; remark: str
    class Config: from_attributes = True

class SiteIn(BaseModel):
    company_code: str = ""; code: str; name: str; name_id: str = ""; region: str = ""
    country: str = "Indonesia"; is_active: bool = True; external_id: str = ""; remark: str = ""

class DivisionOut(BaseModel):
    id: int; company_code: str; site_code: str; code: str; name: str; name_id: str
    is_active: bool; source: str; external_id: str; remark: str
    class Config: from_attributes = True

class DivisionIn(BaseModel):
    company_code: str = ""; site_code: str; code: str; name: str; name_id: str = ""
    is_active: bool = True; external_id: str = ""; remark: str = ""

class DataSourceOut(BaseModel):
    id: int; name: str; description: str; source_type: str
    host: str; port: int; database_name: str; username: str
    api_url: str; api_method: str; api_response_path: str
    sync_query: str; target_entity: str; field_mapping: str
    is_active: bool; last_sync_at: Optional[datetime]; last_sync_count: int
    last_sync_status: str; last_sync_message: str
    class Config: from_attributes = True

class DataSourceIn(BaseModel):
    name: str; description: str = ""; source_type: str
    host: str = ""; port: int = 5432; database_name: str = ""
    username: str = ""; password: str = ""
    api_url: str = ""; api_method: str = "GET"
    api_headers: str = "{}"; api_response_path: str = ""
    sync_query: str = ""; target_entity: str; field_mapping: str = "{}"
    is_active: bool = True

class SyncResult(BaseModel):
    success: bool; count: int; message: str


# ─── DimCompany CRUD ──────────────────────────────────────────────────────────

@router.get("/master/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.scalars(select(DimCompany).order_by(DimCompany.code)).all()

@router.post("/master/companies", response_model=CompanyOut)
def create_company(body: CompanyIn, db: Session = Depends(get_db)):
    if db.scalar(select(DimCompany).where(DimCompany.code == body.code)):
        raise HTTPException(400, f"公司代码 {body.code!r} 已存在")
    obj = DimCompany(**body.model_dump(), source="manual")
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/master/companies/{oid}", response_model=CompanyOut)
def update_company(oid: int, body: CompanyIn, db: Session = Depends(get_db)):
    obj = db.get(DimCompany, oid)
    if not obj: raise HTTPException(404, "公司不存在")
    for k, v in body.model_dump().items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow(); db.commit(); db.refresh(obj)
    return obj

@router.delete("/master/companies/{oid}")
def delete_company(oid: int, db: Session = Depends(get_db)):
    obj = db.get(DimCompany, oid)
    if not obj: raise HTTPException(404, "公司不存在")
    db.delete(obj); db.commit()
    return {"message": "已删除"}


# ─── DimFactory CRUD ──────────────────────────────────────────────────────────

@router.get("/master/factories", response_model=list[FactoryOut])
def list_factories(company_code: str = "", db: Session = Depends(get_db)):
    stmt = select(DimFactory).order_by(DimFactory.company_code, DimFactory.code)
    if company_code: stmt = stmt.where(DimFactory.company_code == company_code)
    return db.scalars(stmt).all()

@router.post("/master/factories", response_model=FactoryOut)
def create_factory(body: FactoryIn, db: Session = Depends(get_db)):
    if db.scalar(select(DimFactory).where(DimFactory.code == body.code)):
        raise HTTPException(400, f"工厂代码 {body.code!r} 已存在")
    obj = DimFactory(**body.model_dump(), source="manual")
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/master/factories/{oid}", response_model=FactoryOut)
def update_factory(oid: int, body: FactoryIn, db: Session = Depends(get_db)):
    obj = db.get(DimFactory, oid)
    if not obj: raise HTTPException(404, "工厂不存在")
    for k, v in body.model_dump().items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow(); db.commit(); db.refresh(obj)
    return obj

@router.delete("/master/factories/{oid}")
def delete_factory(oid: int, db: Session = Depends(get_db)):
    obj = db.get(DimFactory, oid)
    if not obj: raise HTTPException(404, "工厂不存在")
    db.delete(obj); db.commit()
    return {"message": "已删除"}


# ─── DimBlok CRUD ─────────────────────────────────────────────────────────────

@router.get("/master/bloks", response_model=list[BlokOut])
def list_bloks(site_code: str = "", division_code: str = "", db: Session = Depends(get_db)):
    stmt = select(DimBlok).order_by(DimBlok.site_code, DimBlok.division_code, DimBlok.code)
    if site_code: stmt = stmt.where(DimBlok.site_code == site_code)
    if division_code: stmt = stmt.where(DimBlok.division_code == division_code)
    return db.scalars(stmt).all()

@router.post("/master/bloks", response_model=BlokOut)
def create_blok(body: BlokIn, db: Session = Depends(get_db)):
    dup = db.scalar(select(DimBlok).where(
        DimBlok.site_code == body.site_code,
        DimBlok.division_code == body.division_code,
        DimBlok.code == body.code,
    ))
    if dup: raise HTTPException(400, f"地块 {body.code!r} 在该小区已存在")
    obj = DimBlok(**body.model_dump(), source="manual")
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/master/bloks/{oid}", response_model=BlokOut)
def update_blok(oid: int, body: BlokIn, db: Session = Depends(get_db)):
    obj = db.get(DimBlok, oid)
    if not obj: raise HTTPException(404, "地块不存在")
    for k, v in body.model_dump().items(): setattr(obj, k, v)
    obj.updated_at = datetime.utcnow(); db.commit(); db.refresh(obj)
    return obj

@router.delete("/master/bloks/{oid}")
def delete_blok(oid: int, db: Session = Depends(get_db)):
    obj = db.get(DimBlok, oid)
    if not obj: raise HTTPException(404, "地块不存在")
    db.delete(obj); db.commit()
    return {"message": "已删除"}


# ─── DimSite CRUD ─────────────────────────────────────────────────────────────

@router.get("/master/sites", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.scalars(select(DimSite).order_by(DimSite.code)).all()


@router.post("/master/sites", response_model=SiteOut)
def create_site(body: SiteIn, db: Session = Depends(get_db)):
    if db.scalar(select(DimSite).where(DimSite.code == body.code)):
        raise HTTPException(400, f"园区代码 {body.code!r} 已存在")
    site = DimSite(**body.model_dump(), source="manual")
    db.add(site); db.commit(); db.refresh(site)
    return site


@router.put("/master/sites/{site_id}", response_model=SiteOut)
def update_site(site_id: int, body: SiteIn, db: Session = Depends(get_db)):
    site = db.get(DimSite, site_id)
    if not site:
        raise HTTPException(404, "园区不存在")
    dup = db.scalar(select(DimSite).where(DimSite.code == body.code, DimSite.id != site_id))
    if dup:
        raise HTTPException(400, f"园区代码 {body.code!r} 已被其他记录使用")
    for k, v in body.model_dump().items():
        setattr(site, k, v)
    site.updated_at = datetime.utcnow()
    db.commit(); db.refresh(site)
    return site


@router.delete("/master/sites/{site_id}")
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = db.get(DimSite, site_id)
    if not site:
        raise HTTPException(404, "园区不存在")
    db.delete(site); db.commit()
    return {"message": "已删除"}


# ─── DimDivision CRUD ─────────────────────────────────────────────────────────

@router.get("/master/divisions", response_model=list[DivisionOut])
def list_divisions(site_code: str = "", db: Session = Depends(get_db)):
    stmt = select(DimDivision).order_by(DimDivision.site_code, DimDivision.code)
    if site_code:
        stmt = stmt.where(DimDivision.site_code == site_code)
    return db.scalars(stmt).all()


@router.post("/master/divisions", response_model=DivisionOut)
def create_division(body: DivisionIn, db: Session = Depends(get_db)):
    dup = db.scalar(
        select(DimDivision).where(DimDivision.site_code == body.site_code, DimDivision.code == body.code)
    )
    if dup:
        raise HTTPException(400, f"小区代码 {body.code!r} 在该园区已存在")
    div = DimDivision(**body.model_dump(), source="manual")
    db.add(div); db.commit(); db.refresh(div)
    return div


@router.put("/master/divisions/{div_id}", response_model=DivisionOut)
def update_division(div_id: int, body: DivisionIn, db: Session = Depends(get_db)):
    div = db.get(DimDivision, div_id)
    if not div:
        raise HTTPException(404, "小区不存在")
    dup = db.scalar(
        select(DimDivision).where(
            DimDivision.site_code == body.site_code,
            DimDivision.code == body.code,
            DimDivision.id != div_id,
        )
    )
    if dup:
        raise HTTPException(400, "小区代码已被其他记录使用")
    for k, v in body.model_dump().items():
        setattr(div, k, v)
    div.updated_at = datetime.utcnow()
    db.commit(); db.refresh(div)
    return div


@router.delete("/master/divisions/{div_id}")
def delete_division(div_id: int, db: Session = Depends(get_db)):
    div = db.get(DimDivision, div_id)
    if not div:
        raise HTTPException(404, "小区不存在")
    db.delete(div); db.commit()
    return {"message": "已删除"}


# ─── DataSourceConfig CRUD ────────────────────────────────────────────────────

@router.get("/master/data-sources", response_model=list[DataSourceOut])
def list_data_sources(db: Session = Depends(get_db)):
    return db.scalars(select(DataSourceConfig).order_by(DataSourceConfig.id)).all()


@router.post("/master/data-sources", response_model=DataSourceOut)
def create_data_source(body: DataSourceIn, db: Session = Depends(get_db)):
    cfg = DataSourceConfig(
        name=body.name, description=body.description, source_type=body.source_type,
        host=body.host, port=body.port, database_name=body.database_name,
        username=body.username, password_enc=encrypt_secret(body.password),
        api_url=body.api_url, api_method=body.api_method,
        api_headers_enc=encrypt_secret(body.api_headers),
        api_response_path=body.api_response_path,
        sync_query=body.sync_query, target_entity=body.target_entity,
        field_mapping=body.field_mapping, is_active=body.is_active,
    )
    db.add(cfg); db.commit(); db.refresh(cfg)
    return cfg


@router.put("/master/data-sources/{cfg_id}", response_model=DataSourceOut)
def update_data_source(cfg_id: int, body: DataSourceIn, db: Session = Depends(get_db)):
    cfg = db.get(DataSourceConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "数据源不存在")
    cfg.name = body.name; cfg.description = body.description
    cfg.source_type = body.source_type; cfg.host = body.host; cfg.port = body.port
    cfg.database_name = body.database_name; cfg.username = body.username
    if body.password:
        cfg.password_enc = encrypt_secret(body.password)
    cfg.api_url = body.api_url; cfg.api_method = body.api_method
    if body.api_headers and body.api_headers != "{}":
        cfg.api_headers_enc = encrypt_secret(body.api_headers)
    cfg.api_response_path = body.api_response_path
    cfg.sync_query = body.sync_query; cfg.target_entity = body.target_entity
    cfg.field_mapping = body.field_mapping; cfg.is_active = body.is_active
    cfg.updated_at = datetime.utcnow()
    db.commit(); db.refresh(cfg)
    return cfg


@router.delete("/master/data-sources/{cfg_id}")
def delete_data_source(cfg_id: int, db: Session = Depends(get_db)):
    cfg = db.get(DataSourceConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "数据源不存在")
    db.delete(cfg); db.commit()
    return {"message": "已删除"}


# ─── Test connection ───────────────────────────────────────────────────────────

@router.post("/master/data-sources/{cfg_id}/test", response_model=SyncResult)
def test_connection(cfg_id: int, db: Session = Depends(get_db)):
    cfg = db.get(DataSourceConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "数据源不存在")
    try:
        if cfg.source_type in ("postgresql", "sqlserver"):
            _test_db(cfg)
        else:
            _test_rest(cfg)
        return SyncResult(success=True, count=0, message="连接成功")
    except Exception as e:
        return SyncResult(success=False, count=0, message=str(e)[:500])


def _test_db(cfg: DataSourceConfig) -> None:
    password = decrypt_secret(cfg.password_enc)
    if cfg.source_type == "postgresql":
        import psycopg
        conn_info = f"host={cfg.host} port={cfg.port} dbname={cfg.database_name} user={cfg.username} password={password} connect_timeout=8"
        with psycopg.connect(conn_info) as conn:
            conn.execute("SELECT 1")
    else:
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={cfg.host},{cfg.port};DATABASE={cfg.database_name};"
            f"UID={cfg.username};PWD={password};"
            f"Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8"
        )
        with pyodbc.connect(conn_str) as conn:
            conn.execute("SELECT 1")


def _test_rest(cfg: DataSourceConfig) -> None:
    headers = json.loads(decrypt_secret(cfg.api_headers_enc) or "{}")
    resp = http_requests.request(cfg.api_method, cfg.api_url, headers=headers, timeout=10)
    resp.raise_for_status()


# ─── Sync ─────────────────────────────────────────────────────────────────────

@router.post("/master/data-sources/{cfg_id}/sync", response_model=SyncResult)
def run_sync(cfg_id: int, db: Session = Depends(get_db)):
    cfg = db.get(DataSourceConfig, cfg_id)
    if not cfg:
        raise HTTPException(404, "数据源不存在")
    try:
        if cfg.source_type in ("postgresql", "sqlserver"):
            rows = _fetch_from_db(cfg)
        else:
            rows = _fetch_from_rest(cfg)
        count = _upsert_dim(db, cfg.target_entity, rows, json.loads(cfg.field_mapping))
        _update_sync_status(db, cfg, count, "ok", f"同步 {count} 条记录")
        return SyncResult(success=True, count=count, message=f"同步完成，共 {count} 条记录")
    except Exception as e:
        msg = str(e)[:500]
        _update_sync_status(db, cfg, 0, "error", msg)
        return SyncResult(success=False, count=0, message=msg)


def _fetch_from_db(cfg: DataSourceConfig) -> list[dict[str, Any]]:
    password = decrypt_secret(cfg.password_enc)
    if cfg.source_type == "postgresql":
        import psycopg
        conn_info = f"host={cfg.host} port={cfg.port} dbname={cfg.database_name} user={cfg.username} password={password} connect_timeout=8"
        with psycopg.connect(conn_info) as conn:
            with conn.cursor() as cur:
                cur.execute(cfg.sync_query)
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    else:
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={cfg.host},{cfg.port};DATABASE={cfg.database_name};"
            f"UID={cfg.username};PWD={password};"
            f"Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8"
        )
        with pyodbc.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(cfg.sync_query)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetch_from_rest(cfg: DataSourceConfig) -> list[dict[str, Any]]:
    headers = json.loads(decrypt_secret(cfg.api_headers_enc) or "{}")
    resp = http_requests.request(cfg.api_method, cfg.api_url, headers=headers, timeout=15)
    resp.raise_for_status()
    data: Any = resp.json()
    if cfg.api_response_path:
        for key in cfg.api_response_path.split("."):
            data = data[key]
    return data if isinstance(data, list) else [data]


def _upsert_dim(db: Session, target: str, raw_rows: list[dict], field_map: dict[str, str]) -> int:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if target == "dim_site":
        Model, uk = DimSite, ["code"]
    elif target == "dim_division":
        Model, uk = DimDivision, ["site_code", "code"]
    else:
        raise ValueError(f"未知 target_entity: {target!r}")

    count = 0
    now = datetime.utcnow()
    for raw in raw_rows:
        mapped: dict[str, Any] = {}
        for src_col, tgt_field in field_map.items():
            if src_col in raw and raw[src_col] is not None:
                mapped[tgt_field] = raw[src_col]
        if not all(k in mapped for k in uk):
            continue
        mapped.setdefault("source", "sync")
        mapped["updated_at"] = now
        stmt = pg_insert(Model).values(**mapped)
        update_cols = {k: stmt.excluded[k] for k in mapped if k not in uk}
        stmt = stmt.on_conflict_do_update(index_elements=uk, set_=update_cols)
        db.execute(stmt)
        count += 1
    db.commit()
    return count


def _update_sync_status(db: Session, cfg: DataSourceConfig, count: int, status: str, msg: str) -> None:
    cfg.last_sync_at = datetime.utcnow()
    cfg.last_sync_count = count
    cfg.last_sync_status = status
    cfg.last_sync_message = msg
    db.commit()
