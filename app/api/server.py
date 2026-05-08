from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auth_router import router as auth_router
from app.api.routers.broker_router import router as broker_router
from app.api.routers.strategy_router import router as strategy_router
from app.api.routers.bot_router import router as bot_router
from app.api.routers.metrics_router import router as metrics_router
from app.api.routers.dashboard_router import router as dashboard_router
from app.api.deps import get_db
from app.logs import setup_logger
from app.sync import SyncScheduler

setup_logger()

app = FastAPI(
    title="Bot Mr T - Trading Bot API",
    description="""
    ## API REST para la administración del bot de trading automatizado
    
    Esta API proporciona endpoints para:
    
    * **Autenticación** - Login, registro y gestión de usuarios
    * **Broker** - Conexión con Alpaca, gestión de órdenes y posiciones
    * **Bots** - Crear, iniciar, detener y eliminar bots de trading
    * **Estrategias** - Configuración de estrategias de trading
    * **Dashboard** - Métricas y resumen de rendimiento
    * **Métricas** - Estadísticas detalladas de trading
    
    ### Autenticación
    
    La mayoría de los endpoints requieren autenticación mediante JWT token.
    Use el endpoint `/auth/login` para obtener un token de acceso.
    
    ### Entornos
    
    - **Paper Trading**: Entorno de prueba con dinero virtual
    - **Live Trading**: Entorno de producción con dinero real
    """,
    version="1.0.0",
    contact={
        "name": "Bot Mr T",
        "url": "https://github.com/antonio-montalvo/bot-mr-t",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check endpoint"
        },
        {
            "name": "Auth",
            "description": "Autenticación y gestión de usuarios"
        },
        {
            "name": "Broker",
            "description": "Operaciones con el broker (Alpaca): órdenes, posiciones, cuenta"
        },
        {
            "name": "Bot",
            "description": "Gestión del ciclo de vida de bots de trading"
        },
        {
            "name": "Strategy",
            "description": "Configuración de estrategias de trading"
        },
        {
            "name": "Dashboard",
            "description": "Resumen y métricas del dashboard"
        },
        {
            "name": "Metrics",
            "description": "Métricas detalladas de rendimiento y trading"
        }
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(bot_router)
app.include_router(metrics_router)
app.include_router(dashboard_router)

_sync_scheduler: SyncScheduler = None


@app.on_event("startup")
def startup():
    global _sync_scheduler
    db = get_db()
    _sync_scheduler = SyncScheduler(db)
    _sync_scheduler.start()


@app.on_event("shutdown")
def shutdown():
    global _sync_scheduler
    if _sync_scheduler:
        _sync_scheduler.stop()


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
