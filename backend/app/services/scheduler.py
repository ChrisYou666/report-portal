"""
定时同步调度器

使用 APScheduler BackgroundScheduler，从数据库读取 ScheduledSync 配置，
按 cron 表达式触发各类同步任务。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import IndexNotificationConfig, ScheduledSync

logger = logging.getLogger(__name__)

# 全局调度器单例
_scheduler: BackgroundScheduler | None = None


# ── Teams 通知 ────────────────────────────────────────────────────

def _send_teams_notify(job_name: str, status: str, message: str) -> None:
    """向 Teams Webhook 推送同步结果通知（忽略所有错误，不影响主流程）。"""
    import urllib.request
    import json as _json

    db = SessionLocal()
    try:
        from app.models import SystemConfig
        from app.core.config import settings as _settings
        url_cfg     = db.get(SystemConfig, "teams_webhook_url")
        notify_cfg  = db.get(SystemConfig, "teams_notify_on")
        webhook_url = (url_cfg.value if url_cfg and url_cfg.value else None) or _settings.teams_webhook_url
        notify_on   = (notify_cfg.value if notify_cfg else "failure").split(",")
        portal_url  = (_settings.teams_portal_url or "").strip()
        if not webhook_url:
            return
        if status not in notify_on:
            return

        icon  = "✅" if status == "success" else "❌"
        color = "Good" if status == "success" else "Attention"
        label = "成功" if status == "success" else "失败"

        card_body = [
            {"type": "TextBlock", "size": "Medium", "weight": "Bolder",
             "text": f"{icon} 定时同步 {label}：{job_name}"},
            {"type": "TextBlock", "wrap": True, "text": message or "—"},
            {"type": "TextBlock", "isSubtle": True, "size": "Small",
             "text": f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
        ]
        if portal_url:
            card_body.append({
                "type": "TextBlock",
                "wrap": True,
                "spacing": "Medium",
                "text": f"System link: [{portal_url}]({portal_url})",
            })

        payload = _json.dumps({
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard", "version": "1.2",
                    "body": card_body,
                }
            }]
        }).encode()

        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        logger.exception("Teams 通知发送失败（已忽略）")
    finally:
        db.close()


# ── 同步执行器 ────────────────────────────────────────────────────

def _run_sub_metric_sync(job_id: int) -> None:
    """执行单个分项 db_sync"""
    db: Session = SessionLocal()
    job: ScheduledSync | None = None
    try:
        job = db.get(ScheduledSync, job_id)
        if not job or not job.enabled:
            return

        job.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.last_status = "running"
        job.last_message = "同步中…"
        db.commit()

        from app.api.index_mgmt import _run_sm_query  # 避免循环导入
        from app.models import IndexSubMetric, IndexDataEntry

        sm = db.get(IndexSubMetric, job.sub_metric_id)
        if not sm:
            raise ValueError(f"分项 {job.sub_metric_id} 不存在")

        items = _run_sm_query(sm, job.months, db)
        for item in items:
            existing = (
                db.query(IndexDataEntry)
                .filter_by(sub_metric_id=sm.id, period_year=item["year"], period_month=item["month"])
                .first()
            )
            if existing:
                existing.value = item["value"]
                existing.source = "db_sync"
                existing.updated_at = datetime.utcnow()
            else:
                db.add(IndexDataEntry(
                    sub_metric_id=sm.id,
                    period_year=item["year"],
                    period_month=item["month"],
                    value=item["value"],
                    source="db_sync",
                    created_by="scheduler",
                ))
        db.commit()

        from app.core.cache import cache, PFX_INDEX_CALC
        cache.delete_prefix(PFX_INDEX_CALC)

        job.last_status = "success"
        job.last_message = f"写入 {len(items)} 条"

    except Exception as e:
        logger.exception("定时同步 sub_metric job_id=%s 失败", job_id)
        if job:
            job.last_status = "failed"
            job.last_message = str(e)[:500]
    finally:
        if job:
            db.commit()
            _send_teams_notify(job.name, job.last_status or "", job.last_message or "")
        db.close()


def _run_sap_harvest_sync(job_id: int) -> None:
    """触发 SAP 产量管道同步（SQL Server → ODS → DWD → 指标）"""
    db: Session = SessionLocal()
    job: ScheduledSync | None = None
    try:
        job = db.get(ScheduledSync, job_id)
        if not job or not job.enabled:
            return

        job.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.last_status = "running"
        job.last_message = "产量管道同步中…"
        db.commit()

        import uuid, threading
        from app.api.index_mgmt import (
            _run_harvest_sync_job, _find_running_job, SYNC_JOBS, SYNC_LOCK,
        )

        if _find_running_job():
            job.last_status = "failed"
            job.last_message = "已有同步任务在运行，跳过"
            db.commit()
            return

        new_job_id = uuid.uuid4().hex
        sync_record = {
            "job_id": new_job_id, "status": "running",
            "months": job.months,
            "source_tables": [], "current_step": "queued",
            "current_table": "", "current_rows": 0,
            "ods_rows": {}, "dwd_rows": 0,
            "message": "定时触发", "error": "",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None, "logs": [],
        }
        with SYNC_LOCK:
            SYNC_JOBS[new_job_id] = sync_record

        t = threading.Thread(
            target=_run_harvest_sync_job,
            args=(new_job_id, job.months),
            daemon=True,
        )
        t.start()
        t.join(timeout=3600)  # 最多等 1 小时

        with SYNC_LOCK:
            result = SYNC_JOBS.get(new_job_id, {})

        if result.get("status") == "success":
            job.last_status = "success"
            job.last_message = result.get("message", "完成")
        else:
            job.last_status = "failed"
            job.last_message = result.get("error") or result.get("message", "未知错误")

    except Exception as e:
        logger.exception("定时同步 sap_harvest job_id=%s 失败", job_id)
        if job:
            job.last_status = "failed"
            job.last_message = str(e)[:500]
    finally:
        if job:
            db.commit()
            _send_teams_notify(job.name, job.last_status or "", job.last_message or "")
            if job.last_status == "success":
                _send_agri_daily_report(job.name)
        db.close()


def _run_agri_production_sync(job_id: int) -> None:
    """同步农业产量分项数据"""
    db: Session = SessionLocal()
    job: ScheduledSync | None = None
    try:
        job = db.get(ScheduledSync, job_id)
        if not job or not job.enabled:
            return

        job.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.last_status = "running"
        job.last_message = "农业产量同步中…"
        db.commit()

        from app.api.agri_index import _compute_agri_cumulative
        from app.models import IndexDataEntry

        if not job.sub_metric_id:
            raise ValueError("未配置 sub_metric_id")

        items = _compute_agri_cumulative(job.months, db)
        count = 0
        for item in items:
            existing = (
                db.query(IndexDataEntry)
                .filter_by(sub_metric_id=job.sub_metric_id, period_year=item["year"], period_month=item["month"])
                .first()
            )
            if existing:
                existing.value = item["value"]
                existing.source = "db_sync"
                existing.updated_at = datetime.utcnow()
            else:
                db.add(IndexDataEntry(
                    sub_metric_id=job.sub_metric_id,
                    period_year=item["year"],
                    period_month=item["month"],
                    value=item["value"],
                    source="db_sync",
                    created_by="scheduler",
                ))
            count += 1
        db.commit()

        from app.core.cache import cache, PFX_INDEX_CALC
        cache.delete_prefix(PFX_INDEX_CALC)

        job.last_status = "success"
        job.last_message = f"写入 {count} 条"

    except Exception as e:
        logger.exception("定时同步 agri_production job_id=%s 失败", job_id)
        if job:
            job.last_status = "failed"
            job.last_message = str(e)[:500]
    finally:
        if job:
            db.commit()
            _send_teams_notify(job.name, job.last_status or "", job.last_message or "")
            if job.last_status == "success":
                _send_agri_daily_report(job.name)
        db.close()


def _send_agri_daily_report(job_name: str) -> None:
    """查询最新日度农业数据并推送到 Teams。"""
    import urllib.request
    import json as _json

    db = SessionLocal()
    try:
        from app.models import SystemConfig
        from app.core.config import settings as _settings
        from sqlalchemy import text

        url_cfg     = db.get(SystemConfig, "teams_webhook_url")
        notify_cfg  = db.get(SystemConfig, "teams_notify_on")
        webhook_url = (url_cfg.value if url_cfg and url_cfg.value else None) or _settings.teams_webhook_url
        notify_on   = (notify_cfg.value if notify_cfg else "success,failure").split(",")
        portal_url  = (_settings.teams_portal_url or "").strip()
        if not webhook_url or "success" not in notify_on:
            return

        # ── 查 DWD 最新一天汇总 ──
        row = db.execute(text("""
            select
                date,
                round(sum(production_bg)::numeric, 0)  as prod_bg,
                round(sum(production_ag)::numeric, 0)  as prod_ag,
                count(distinct estate_code)            as estate_count
            from dwd.sap_harvest_actual_block_daily
            where date = (select max(date) from dwd.sap_harvest_actual_block_daily)
            group by date
        """)).fetchone()

        if not row:
            return

        latest_date  = row.date.strftime("%Y-%m-%d") if hasattr(row.date, 'strftime') else str(row.date)
        prod_bg      = int(row.prod_bg or 0)
        prod_ag      = int(row.prod_ag or 0)
        estate_count = int(row.estate_count or 0)

        # ── 查各园区分项明细（前10个园区）──
        estate_rows = db.execute(text("""
            select
                h.estate_code,
                coalesce(max(e.name1), h.estate_code) as estate_name,
                round(sum(h.production_bg)::numeric, 0) as prod_bg,
                round(sum(h.production_ag)::numeric, 0) as prod_ag
            from dwd.sap_harvest_actual_block_daily h
            left join ods.sap_stg_zest_estate e
                   on e.estnr = h.estate_code
            where h.date = (select max(date) from dwd.sap_harvest_actual_block_daily)
            group by h.estate_code
            order by prod_bg desc
            limit 10
        """)).fetchall()

        # ── 格式化 Adaptive Card ──
        def fmt_num(n: int) -> str:
            return f"{n:,}"

        facts = [
            {"title": "产量合计（扣重前）", "value": f"{fmt_num(prod_bg)} kg"},
            {"title": "产量合计（扣重后）", "value": f"{fmt_num(prod_ag)} kg"},
            {"title": "有数据园区数",       "value": f"{estate_count} 个"},
        ]

        # 园区明细行（ColumnSet 表格）
        estate_columns = [
            {"type": "Column", "width": "stretch", "items": [
                {"type": "TextBlock", "text": "**园区**", "size": "Small", "weight": "Bolder"},
                *[{"type": "TextBlock", "text": f"{r.estate_name}（{r.estate_code}）",
                   "size": "Small", "wrap": True} for r in estate_rows],
            ]},
            {"type": "Column", "width": "auto", "items": [
                {"type": "TextBlock", "text": "**扣重前(kg)**", "size": "Small", "weight": "Bolder", "horizontalAlignment": "Right"},
                *[{"type": "TextBlock", "text": fmt_num(int(r.prod_bg or 0)),
                   "size": "Small", "horizontalAlignment": "Right"} for r in estate_rows],
            ]},
            {"type": "Column", "width": "auto", "items": [
                {"type": "TextBlock", "text": "**扣重后(kg)**", "size": "Small", "weight": "Bolder", "horizontalAlignment": "Right"},
                *[{"type": "TextBlock", "text": fmt_num(int(r.prod_ag or 0)),
                   "size": "Small", "horizontalAlignment": "Right"} for r in estate_rows],
            ]},
        ]

        card_body = [
            {"type": "TextBlock", "size": "Large", "weight": "Bolder",
             "text": f"🌿 每日农业指标 — {latest_date}"},
            {"type": "FactSet", "facts": facts},
            {"type": "TextBlock", "text": "**各园区产量明细**", "size": "Small",
             "weight": "Bolder", "spacing": "Medium"},
            {"type": "ColumnSet", "columns": estate_columns},
            {"type": "TextBlock", "isSubtle": True, "size": "Small", "spacing": "Medium",
             "text": f"来源任务：{job_name}  |  推送时间：{datetime.now().strftime('%H:%M:%S')}"},
        ]
        if portal_url:
            card_body.append({
                "type": "TextBlock",
                "wrap": True,
                "spacing": "Medium",
                "text": f"System link: [{portal_url}]({portal_url})",
            })

        payload = _json.dumps({
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard", "version": "1.2",
                    "body": card_body,
                }
            }]
        }).encode()

        req = urllib.request.Request(
            webhook_url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("农业日报已推送到 Teams，日期=%s", latest_date)

    except Exception:
        logger.exception("农业日报 Teams 推送失败（已忽略）")
    finally:
        db.close()


_RUNNERS = {
    "sub_metric":      _run_sub_metric_sync,
    "sap_harvest":     _run_sap_harvest_sync,
    "agri_production": _run_agri_production_sync,
}


def _run_index_notification(config_id: int) -> None:
    db: Session = SessionLocal()
    try:
        from app.services.index_notifications import send_index_notification

        send_index_notification(db, config_id)
    except Exception:
        logger.exception("指标 Teams Bot 通知发送失败 config_id=%s", config_id)
    finally:
        db.close()


# ── 调度器管理 ────────────────────────────────────────────────────

def _load_jobs(scheduler: BackgroundScheduler) -> None:
    """从数据库读取所有启用的定时任务并注册到调度器。"""
    db = SessionLocal()
    try:
        jobs: list[ScheduledSync] = db.query(ScheduledSync).filter_by(enabled=True).all()
        for job in jobs:
            _add_job(scheduler, job)
        index_jobs: list[IndexNotificationConfig] = (
            db.query(IndexNotificationConfig).filter_by(enabled=True).all()
        )
        for cfg in index_jobs:
            _add_index_notification_job(scheduler, cfg)
        logger.info("定时调度器：已加载 %d 个同步任务，%d 个指标通知任务", len(jobs), len(index_jobs))
    finally:
        db.close()


def _add_job(scheduler: BackgroundScheduler, job: ScheduledSync) -> None:
    runner = _RUNNERS.get(job.sync_type)
    if not runner:
        return
    try:
        scheduler.add_job(
            runner,
            trigger=CronTrigger(
                minute=job.cron_minute,
                hour=job.cron_hour,
                day=job.cron_day,
                month=job.cron_month,
                day_of_week=job.cron_dow,
            ),
            args=[job.id],
            id=f"sync_{job.id}",
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception:
        logger.exception("注册定时任务 id=%s 失败", job.id)


def _add_index_notification_job(scheduler: BackgroundScheduler, cfg: IndexNotificationConfig) -> None:
    try:
        scheduler.add_job(
            _run_index_notification,
            trigger=CronTrigger(
                minute=cfg.cron_minute,
                hour=cfg.cron_hour,
                day=cfg.cron_day,
                month=cfg.cron_month,
                day_of_week=cfg.cron_dow,
            ),
            args=[cfg.id],
            id=f"index_notify_{cfg.id}",
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception:
        logger.exception("注册指标通知任务 id=%s code=%s 失败", cfg.id, cfg.index_code)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Kuala_Lumpur")
    _load_jobs(_scheduler)
    _scheduler.start()
    logger.info("定时调度器已启动")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def reload_job(job: ScheduledSync) -> None:
    """在 API 保存/更新任务后刷新调度器注册。"""
    if not _scheduler:
        return
    job_id = f"sync_{job.id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    if job.enabled:
        _add_job(_scheduler, job)


def remove_job(sync_id: int) -> None:
    if not _scheduler:
        return
    job_id = f"sync_{sync_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


def reload_index_notification(cfg: IndexNotificationConfig) -> None:
    if not _scheduler:
        return
    job_id = f"index_notify_{cfg.id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    if cfg.enabled:
        _add_index_notification_job(_scheduler, cfg)
