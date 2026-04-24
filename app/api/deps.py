from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.api.config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
)
from app.auth import AlpacaAuth
from app.broker import AlpacaBroker
from app.orders import OrderManager
from app.positions import PositionManager
from app.risk import RiskManager
from app.db import Database

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[str]:
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return username
    return None


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
