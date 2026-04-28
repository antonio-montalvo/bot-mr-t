from fastapi import APIRouter, HTTPException, status

from app.api.schemas import LoginRequest, TokenResponse, RefreshRequest, RegisterRequest, UserResponse
from app.api.deps import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    user = create_user(email=body.email, password=body.password, full_name=body.full_name)
    return UserResponse(**user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenResponse(
        access_token=create_access_token(user["email"]),
        refresh_token=create_refresh_token(user["email"]),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    email = decode_refresh_token(body.refresh_token)
    return TokenResponse(
        access_token=create_access_token(email),
        refresh_token=create_refresh_token(email),
    )
