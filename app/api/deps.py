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
_risk_manager: Optional[RiskManager] = None
_db: Optional[Database] = None


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
def create_access_token(subject: str, user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "uid": user_id, "exp": expire, "type": "access"}, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str, user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "uid": user_id, "exp": expire, "type": "refresh"}, SECRET_KEY, algorithm=ALGORITHM)


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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("uid")
        token_type: str = payload.get("type")
        if email is None or user_id is None or token_type != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return {"id": user_id, "email": email}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("uid")
        token_type: str = payload.get("type")
        if email is None or user_id is None or token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
        return {"id": user_id, "email": email}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido o expirado")


# ── Per-user Alpaca dependencies ─────────────────
def get_user_api_keys(user_id: str) -> dict:
    db = get_db()
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT api_key_encrypted, secret_key_encrypted, broker_name, environment "
        "FROM api_keys WHERE user_id = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron API keys activas para este usuario",
        )
    return {
        "api_key": row[0],
        "secret_key": row[1],
        "broker_name": row[2],
        "environment": row[3],
    }


def get_alpaca_auth(current_user: dict = Depends(get_current_user)) -> AlpacaAuth:
    keys = get_user_api_keys(current_user["id"])
    return AlpacaAuth(api_key=keys["api_key"], secret_key=keys["secret_key"])


def get_broker(auth: AlpacaAuth = Depends(get_alpaca_auth)) -> AlpacaBroker:
    return AlpacaBroker(auth)


def get_order_manager(auth: AlpacaAuth = Depends(get_alpaca_auth)) -> OrderManager:
    return OrderManager(auth.client)


def get_position_manager(auth: AlpacaAuth = Depends(get_alpaca_auth)) -> PositionManager:
    return PositionManager(auth.client)
