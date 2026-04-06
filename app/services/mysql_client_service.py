"""
MySQL Database Client Service

Centralized MySQL connection and query execution for Healoncal.
Designed to work with both Cloud SQL for MySQL (via private IP or Unix socket)
and Docker MySQL running on GCP or locally.
"""
import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """Types MySQL rows often contain that stdlib json cannot encode."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if type(obj).__name__ in ("bool_",) and hasattr(obj, "item"):  # numpy.bool_
        return bool(obj)
    if hasattr(obj, "item") and callable(getattr(obj, "item")):
        try:
            return obj.item()
        except Exception:
            pass
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps_json(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)

# JSON columns per table (for serialization on insert/update)
_TABLE_JSON_COLUMNS = {
    "healoncal_analysis_sessions": ["device_info", "location_info"],
    "healoncal_captured_images": [],
    "healoncal_analysis_results": [
        "treatment_recommendations", "personalized_routine", "analysis_data"
    ],
    "treatment_recommendations": [
        "products", "routine_steps", "key_advice", "ingredients_to_avoid",
        "primary_skin_concerns", "user_preferences", "medical_flags",
        "user_feedback"
    ],
    "detected_skin_diseases": [
        "symptoms_noted", "risk_factors", "differential_diagnoses",
        "treatment_recommended", "contraindications", "image_regions",
        "biomarker_correlations"
    ],
    "disease_heatmaps": ["colors"],
}


def _serialize_value(key: str, value: Any, table: str) -> Any:
    """Serialize a value for MySQL (e.g. dict/list -> JSON string)."""
    if value is None:
        return None
    if table in _TABLE_JSON_COLUMNS and key in _TABLE_JSON_COLUMNS[table]:
        if isinstance(value, (dict, list)):
            if not value:
                return "{}" if isinstance(value, dict) else "[]"
            return _dumps_json(value)
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def _row_for_insert(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare row for INSERT: JSON columns as strings, bools as 0/1."""
    out = {}
    for k, v in row.items():
        if v is None:
            continue
        out[k] = _serialize_value(k, v, table)
    return out


class MySQLClientService:
    """MySQL connection pool and query execution."""

    _instance = None
    _pool = None
    _available = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._init_pool()

    def _init_pool(self):
        try:
            from app.core.config import settings
            import pymysql
            from pymysql.cursors import DictCursor

            host = getattr(settings, "MYSQL_HOST", None)
            user = getattr(settings, "MYSQL_USER", None)
            database = getattr(settings, "MYSQL_DATABASE", None)
            unix_socket = getattr(settings, "MYSQL_UNIX_SOCKET", None)

            # Allow either TCP (host/port) or Unix socket (for Cloud SQL connector)
            if not database or not user or (not host and not unix_socket):
                logger.warning("[MYSQL] Not configured (need MYSQL_USER, MYSQL_DATABASE and either MYSQL_HOST or MYSQL_UNIX_SOCKET) - running without DB")
                self._available = False
                return

            self._pymysql = pymysql
            self._DictCursor = DictCursor

            base_cfg = {
                "user": user or "",
                "password": getattr(settings, "MYSQL_PASSWORD", "") or "",
                "database": database or "",
                "charset": "utf8mb4",
                "cursorclass": DictCursor,
                "autocommit": True,
            }
            if unix_socket:
                base_cfg["unix_socket"] = unix_socket
            else:
                base_cfg["host"] = host or "localhost"
                base_cfg["port"] = int(getattr(settings, "MYSQL_PORT", 3306))

            self._config = base_cfg
            self._available = True
            logger.info("[MYSQL] Client configured successfully (socket=%s, host=%s, port=%s)", bool(unix_socket), base_cfg.get("host"), base_cfg.get("port"))
        except Exception as e:
            logger.warning(f"[MYSQL] Failed to configure: {e}")
            self._available = False

    def reinitialize(self):
        """Reload config and reinit pool (e.g. after loading secrets)."""
        self._init_pool()

    def is_available(self) -> bool:
        return self._available is True

    def get_connection(self):
        """Get a new connection (caller must close or use as context)."""
        if not self._available:
            raise RuntimeError("MySQL is not configured")
        return self._pymysql.connect(**self._config)

    def fetch_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute SELECT and return list of dicts."""
        if not self._available:
            return []
        params = params or ()
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return list(rows) if rows else []
        except Exception as e:
            logger.error(f"[MYSQL] fetch_all error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def fetch_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Execute SELECT and return one row as dict or None."""
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT/UPDATE/DELETE; return affected row count."""
        if not self._available:
            raise RuntimeError("MySQL is not configured")
        params = params or ()
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount
        finally:
            if conn:
                conn.close()

    def insert(self, table: str, row: Dict[str, Any]) -> Optional[str]:
        """
        INSERT one row. JSON columns and booleans are serialized.
        If row has 'id' it is used; otherwise id is generated for UUID tables.
        Returns the id of the inserted row.
        """
        if not self._available:
            raise RuntimeError("MySQL is not configured")
        tables_with_uuid_id = [
            "healoncal_analysis_sessions", "healoncal_captured_images",
            "healoncal_analysis_results",
            "treatment_recommendations", "detected_skin_diseases", "disease_heatmaps",
        ]
        if table in tables_with_uuid_id and "id" not in row:
            row = {**row, "id": str(uuid.uuid4())}
        prepared = _row_for_insert(table, row)
        if not prepared:
            return None
        cols = ", ".join(prepared.keys())
        placeholders = ", ".join(["%s"] * len(prepared))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        params = tuple(prepared.values())
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
            return prepared.get("id")
        finally:
            if conn:
                conn.close()

    def update(self, table: str, set_dict: Dict[str, Any], where_col: str, where_val: Any) -> int:
        """UPDATE table SET ... WHERE where_col = where_val. set_dict values are serialized for JSON/bool."""
        if not self._available:
            raise RuntimeError("MySQL is not configured")
        prepared = _row_for_insert(table, set_dict)
        if not prepared:
            return 0
        set_clause = ", ".join(f"{k} = %s" for k in prepared.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_col} = %s"
        params = tuple(prepared.values()) + (where_val,)
        return self.execute(sql, params)


# Global instance
mysql_service = MySQLClientService()
