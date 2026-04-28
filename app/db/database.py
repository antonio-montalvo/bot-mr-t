import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def _get_database_url() -> str:
    return os.getenv("DATABASE_URL")


def _use_postgres() -> bool:
    url = _get_database_url()
    return url is not None and url.startswith("postgresql")


class Database:
    """Gestión de base de datos PostgreSQL (producción) o SQLite (desarrollo local)."""

    def __init__(self):
        self.conn = None
        self._is_postgres = _use_postgres()

    def connect(self):
        if self._is_postgres:
            import psycopg2
            self.conn = psycopg2.connect(_get_database_url())
            logger.info("Conexión a PostgreSQL establecida.")
        else:
            import sqlite3
            db_path = Path(__file__).resolve().parent.parent.parent / "data" / "bot.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path))
            self.conn.row_factory = sqlite3.Row
            logger.info("Conexión a SQLite establecida: %s", db_path)
        self._create_tables()

    def _create_tables(self):
        if self._is_postgres:
            ddl_path = Path(__file__).resolve().parent.parent.parent / "resources" / "ddl.sql"
            if ddl_path.exists():
                sql = ddl_path.read_text(encoding="utf-8")
                cursor = self.conn.cursor()
                cursor.execute(sql)
                self.conn.commit()
                logger.info("DDL ejecutado desde %s", ddl_path)
            else:
                logger.warning("Archivo DDL no encontrado: %s", ddl_path)
        else:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL,
                    order_id TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()

    def insert_trade(self, symbol: str, side: str, qty: float, price: float, order_id: str, status: str):
        cursor = self.conn.cursor()
        placeholder = "%s" if self._is_postgres else "?"
        cursor.execute(
            f"INSERT INTO trades (symbol, side, qty, price, order_id, status) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
            (symbol, side, qty, price, order_id, status),
        )
        self.conn.commit()

    def get_trades(self, limit: int = 50):
        cursor = self.conn.cursor()
        placeholder = "%s" if self._is_postgres else "?"
        cursor.execute(f"SELECT * FROM trades ORDER BY created_at DESC LIMIT {placeholder}", (limit,))
        return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Conexión a base de datos cerrada.")
