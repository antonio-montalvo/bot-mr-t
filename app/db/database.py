import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


def _use_postgres() -> bool:
    return DATABASE_URL is not None and DATABASE_URL.startswith("postgresql")


class Database:
    """Gestión de base de datos PostgreSQL (producción) o SQLite (desarrollo local)."""

    def __init__(self):
        self.conn = None
        self._is_postgres = _use_postgres()

    def connect(self):
        if self._is_postgres:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL)
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
        cursor = self.conn.cursor()
        if self._is_postgres:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    qty DOUBLE PRECISION NOT NULL,
                    price DOUBLE PRECISION,
                    order_id VARCHAR(100),
                    status VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    type VARCHAR(50) NOT NULL,
                    parameters TEXT,
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    type TEXT NOT NULL,
                    parameters TEXT,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
