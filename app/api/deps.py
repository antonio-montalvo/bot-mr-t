from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt

from app.api.config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
)
from app.auth import AlpacaAuth
from app.broker import AlpacaBroker
from app.orders import OrderManager
from app.positions import PositionManager
from app.risk import RiskManager
from app.db import Database

security = HTTPBearer()

# ── Singletons ───────────────────────────────────
_auth: Optional[AlpacaAuth] = None
_broker: Optional[AlpacaBroker] = None
_order_manager: Optional[OrderManager] = None
_position_manager: Optional[PositionManager] = None
_risk_manager: Optional[RiskManager] = None
_db: Optional[Database] = None


def get_alpaca_auth() -> AlpacaAuth:
    global _auth
    if _auth is None:
        _auth = AlpacaAuth()
    return _auth


def get_broker() -> AlpacaBroker:
    global _broker
    if _broker is None:
        _broker = AlpacaBroker(get_alpaca_auth())
    return _broker


def get_order_manager() -> OrderManager:
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager(get_alpaca_auth().client)
    return _order_manager


def get_position_manager() -> PositionManager:
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager(get_alpaca_auth().client)
    return _position_manager


def get_risk_manager() -> RiskManager:
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
        _db.connect()
    return _db


# ── JWT Helpers ──────────────────────────────────
def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire, "type": "access"}, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire, "type": "refresh"}, SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def authenticate_user(email: str, password: str) -> Optional[dict]:
    db = get_db()
    cursor = db.conn.cursor()
    cursor.execute("SELECT id, email, password_hash, full_name, is_active FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    if row is None:
        return None
    user_id, user_email, password_hash, full_name, is_active = row
    if not is_active:
        return None
    if not verify_password(password, password_hash):
        return None
    return {"id": str(user_id), "email": user_email, "full_name": full_name}


def create_user(email: str, password: str, full_name: str = None) -> dict:
    db = get_db()
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")
    hashed = get_password_hash(password)
    cursor.execute(
        "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) RETURNING id, email, full_name, is_active, created_at",
        (email, hashed, full_name),
    )
    row = cursor.fetchone()
    db.conn.commit()
    return {"id": str(row[0]), "email": row[1], "full_name": row[2], "is_active": row[3], "created_at": row[4]}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


def decode_refresh_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido o expirado")
