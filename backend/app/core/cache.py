"""
轻量进程内 TTL 缓存。

特性：
- 线程安全（threading.Lock）
- 支持 TTL 自动过期
- 支持前缀批量失效（写操作触发）
- 单例 `cache`，全进程共享
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Optional


class SimpleCache:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._lock  = threading.Lock()

    # ── 读 ────────────────────────────────────────────────────
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if datetime.utcnow() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["value"]

    # ── 写 ────────────────────────────────────────────────────
    def set(self, key: str, value: Any, ttl: int = 300) -> Any:
        expires = datetime.utcnow() + timedelta(seconds=ttl)
        with self._lock:
            self._store[key] = {"value": value, "expires_at": expires}
        return value

    # ── 失效 ──────────────────────────────────────────────────
    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        """删除所有以 prefix 开头的 key，返回删除数量。"""
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    # ── 统计 ──────────────────────────────────────────────────
    def stats(self) -> dict:
        now = datetime.utcnow()
        with self._lock:
            total   = len(self._store)
            valid   = sum(1 for e in self._store.values() if e["expires_at"] > now)
            keys    = list(self._store.keys())
        return {
            "total": total,
            "valid": valid,
            "expired": total - valid,
            "keys": keys,
        }


# ── 全局单例 ──────────────────────────────────────────────────
cache = SimpleCache()

# ── TTL 常量（秒） ────────────────────────────────────────────
TTL_MONITOR   = 300    # 数据监控：5 分钟
TTL_INDEX_CALC = 60   # 指数计算：1 分钟（写操作会主动失效）
TTL_INDICES   = 600    # 指标定义列表：10 分钟
TTL_DB_SCHEMA = 3600   # DB schema 表/列：1 小时
TTL_DAILY     = 120    # 日度计算：2 分钟

# ── Key 前缀（用于批量失效） ──────────────────────────────────
PFX_MONITOR    = "monitor"
PFX_INDEX_CALC = "index_calc:"
PFX_INDICES    = "indices"
PFX_DB_TABLES  = "db_tables"
PFX_DB_COLS    = "db_cols:"
PFX_DAILY      = "daily:"
