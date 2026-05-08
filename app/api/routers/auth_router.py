from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    LoginRequest, TokenResponse, RefreshRequest,
    RegisterRequest, UserResponse,
    ApiKeyCreate, ApiKeyResponse,
)
from app.api.deps import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    create_user,
    get_current_user,
    get_db,
)
from app.api.crypto import encrypt

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description="Crea una nueva cuenta de usuario en el sistema",
    responses={
        201: {"description": "Usuario creado exitosamente"},
        400: {"description": "Email ya registrado o datos inválidos"}
    }
)
def register(body: RegisterRequest):
    """Registra un nuevo usuario con email, contraseña y nombre completo."""
    user = create_user(email=body.email, password=body.password, full_name=body.full_name)
    return UserResponse(**user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description="Autentica un usuario y devuelve tokens JWT de acceso y refresh",
    responses={
        200: {"description": "Login exitoso, tokens generados"},
        401: {"description": "Credenciales inválidas"}
    }
)
def login(body: LoginRequest):
    """Autentica con email y contraseña, devuelve access_token y refresh_token."""
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenResponse(
        access_token=create_access_token(user["email"], user["id"]),
        refresh_token=create_refresh_token(user["email"], user["id"]),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refrescar token",
    description="Genera nuevos tokens de acceso usando un refresh token válido",
    responses={
        200: {"description": "Tokens refrescados exitosamente"},
        401: {"description": "Refresh token inválido o expirado"}
    }
)
def refresh(body: RefreshRequest):
    """Renueva los tokens de autenticación usando un refresh_token válido."""
    user = decode_refresh_token(body.refresh_token)
    return TokenResponse(
        access_token=create_access_token(user["email"], user["id"]),
        refresh_token=create_refresh_token(user["email"], user["id"]),
    )


@router.post(
    "/api-keys",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear API keys del broker",
    description="Registra las credenciales del broker (Alpaca) para el usuario autenticado",
    responses={
        201: {"description": "API keys guardadas exitosamente"},
        401: {"description": "No autenticado"}
    }
)
def create_api_key(body: ApiKeyCreate, current_user: dict = Depends(get_current_user)):
    """Guarda las API keys del broker de forma encriptada para el usuario actual."""
    db = get_db()
    cursor = db.conn.cursor()
    cursor.execute(
        "INSERT INTO api_keys (user_id, broker_name, environment, api_key_encrypted, secret_key_encrypted) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id, broker_name, environment, is_active, created_at",
        (
            current_user["id"],
            body.broker_name,
            body.environment,
            encrypt(body.api_key),
            encrypt(body.secret_key),
        ),
    )
    row = cursor.fetchone()
    db.conn.commit()
    return ApiKeyResponse(
        id=str(row[0]), broker_name=row[1], environment=row[2],
        is_active=row[3], created_at=row[4],
    )
