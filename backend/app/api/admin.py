"""
admin.py — 系统管理接口（仅限 admin）
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.deps import require_admin
from app.db import engine
from app.models import User

router = APIRouter(tags=["admin"])

# SQL 文件位于 backend/ 根目录
_SQL_FILE = Path(__file__).parent.parent.parent / "init_postgresql.sql"

# 独立出现时跳过（文件里的 BEGIN/COMMIT 交给 engine.begin() 处理）
_SKIP = {"begin", "commit", "rollback"}


def _parse_statements(content: str) -> list[str]:
    """把 SQL 文件拆成可逐条执行的语句列表。"""
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        # 跳过 psql 元命令（\set, \i, \c 等）
        if stripped.startswith("\\"):
            continue
        lines.append(line)

    # 以分号为分隔符拆分语句
    raw_stmts = "\n".join(lines).split(";")
    result: list[str] = []
    for raw in raw_stmts:
        # 去掉纯注释行和空白
        non_comment = "\n".join(
            l for l in raw.splitlines()
            if not l.strip().startswith("--")
        ).strip()
        if not non_comment:
            continue
        # 跳过独立的事务控制语句
        if non_comment.strip().lower() in _SKIP:
            continue
        result.append(non_comment)
    return result


@router.post("/admin/init-db")
def init_db_from_sql(_: User = Depends(require_admin)) -> dict:
    """
    读取项目根目录下的 init_postgresql.sql 并逐条执行。
    幂等：所有建表语句使用 IF NOT EXISTS，插入语句使用 ON CONFLICT DO NOTHING。
    """
    if not _SQL_FILE.exists():
        raise HTTPException(404, f"初始化脚本不存在：{_SQL_FILE}")

    content = _SQL_FILE.read_text(encoding="utf-8")
    statements = _parse_statements(content)

    executed = 0
    skipped = 0
    errors: list[str] = []

    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
                executed += 1
            except Exception as e:
                err_msg = str(e).split("\n")[0][:300]
                # IF NOT EXISTS / ON CONFLICT 失败视为跳过
                if "already exists" in err_msg.lower() or "duplicate" in err_msg.lower():
                    skipped += 1
                else:
                    errors.append(err_msg)

    return {
        "ok": len(errors) == 0,
        "executed": executed,
        "skipped": skipped,
        "errors": errors,
        "message": (
            f"执行 {executed} 条语句，跳过 {skipped} 条，{len(errors)} 个错误"
            if errors else
            f"初始化完成：执行 {executed} 条语句"
        ),
    }


@router.get("/admin/init-db/preview")
def preview_init_sql(_: User = Depends(require_admin)) -> dict:
    """返回 SQL 文件的语句数量和文件信息（用于前端预览确认）。"""
    if not _SQL_FILE.exists():
        raise HTTPException(404, "初始化脚本不存在")
    content = _SQL_FILE.read_text(encoding="utf-8")
    stmts = _parse_statements(content)
    size_kb = round(_SQL_FILE.stat().st_size / 1024, 1)
    return {
        "file": _SQL_FILE.name,
        "size_kb": size_kb,
        "statement_count": len(stmts),
    }
