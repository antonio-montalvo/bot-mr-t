import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bot.db"


class Database:
    """Gestión de base de datos SQLite para persistir trades e historial."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Conexión a base de datos establecida: %s", self.db_path)

    def _create_tables(self):
        cursor = self.conn.cursor()
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
        cursor.execute(
            "INSERT INTO trades (symbol, side, qty, price, order_id, status) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, side, qty, price, order_id, status),
        )
        self.conn.commit()

    def get_trades(self, limit: int = 50):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,))
        return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Conexión a base de datos cerrada.")
