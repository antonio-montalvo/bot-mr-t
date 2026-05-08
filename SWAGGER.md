# Documentación API - Swagger UI

## Acceso a Swagger UI

La API de Bot Mr T incluye documentación interactiva completa mediante Swagger UI (OpenAPI).

### URLs de acceso

Una vez que el servidor esté corriendo, puedes acceder a la documentación en:

- **Swagger UI (interfaz interactiva)**: http://localhost:8000/docs
- **ReDoc (documentación alternativa)**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Iniciar el servidor

```bash
cd c:\workspace-python\bot-mr-t
.venv\Scripts\activate
uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000
```

## Características de Swagger UI

### 1. Exploración de endpoints

Swagger UI organiza todos los endpoints por categorías:

- **Health** - Health check
- **Auth** - Autenticación y gestión de usuarios
- **Broker** - Operaciones con Alpaca (órdenes, posiciones, cuenta)
- **Bot** - Gestión de bots de trading
- **Strategy** - Configuración de estrategias
- **Dashboard** - Resumen y métricas
- **Metrics** - Estadísticas detalladas

### 2. Pruebas interactivas

Puedes probar cada endpoint directamente desde Swagger UI:

1. Haz clic en un endpoint para expandirlo
2. Haz clic en "Try it out"
3. Completa los parámetros requeridos
4. Haz clic en "Execute"
5. Revisa la respuesta

### 3. Autenticación

La mayoría de los endpoints requieren autenticación JWT:

1. **Obtener token**:
   - Ve a `POST /auth/login`
   - Ingresa email y password
   - Copia el `access_token` de la respuesta

2. **Autorizar en Swagger**:
   - Haz clic en el botón "Authorize" (candado) en la parte superior
   - Ingresa: `Bearer {tu_access_token}`
   - Haz clic en "Authorize"

3. Ahora puedes usar todos los endpoints protegidos

### 4. Schemas y modelos

Swagger UI muestra automáticamente:

- Estructura de las peticiones (request body)
- Estructura de las respuestas (response models)
- Validaciones y tipos de datos
- Campos opcionales vs requeridos

## Endpoints principales

### Autenticación

- `POST /auth/register` - Registrar nuevo usuario
- `POST /auth/login` - Iniciar sesión (obtener tokens)
- `POST /auth/refresh` - Refrescar tokens
- `POST /auth/api-keys` - Guardar API keys del broker

### Bots

- `GET /bot/bots` - Listar bots del usuario
- `POST /bot/create` - Crear nuevo bot
- `POST /bot/start` - Iniciar bot
- `POST /bot/stop` - Detener bot
- `GET /bot/status` - Obtener estado del bot
- `DELETE /bot/{bot_id}` - Eliminar bot

### Broker (Alpaca)

- `GET /broker/account` - Información de la cuenta
- `GET /broker/positions` - Posiciones abiertas
- `GET /broker/orders` - Historial de órdenes
- `POST /broker/order` - Crear nueva orden

### Dashboard

- `GET /dashboard/summary` - Resumen completo del bot

### Métricas

- `GET /metrics/performance` - Métricas de rendimiento
- `GET /metrics/trades` - Estadísticas de trades

## Ejemplos de uso

### 1. Flujo completo de autenticación

```bash
# 1. Registrar usuario
POST /auth/register
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}

# 2. Login
POST /auth/login
{
  "email": "user@example.com",
  "password": "securepassword"
}

# Respuesta:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc..."
}

# 3. Guardar API keys del broker
POST /auth/api-keys
Authorization: Bearer eyJhbGc...
{
  "broker_name": "alpaca",
  "environment": "paper",
  "api_key": "PK...",
  "secret_key": "..."
}
```

### 2. Crear y gestionar un bot

```bash
# 1. Crear bot
POST /bot/create
Authorization: Bearer eyJhbGc...
{
  "name": "Bot Mr T - Production",
  "broker_name": "alpaca",
  "environment": "paper"
}

# Respuesta:
{
  "id": "03008cda-1f72-4137-9d6b-279d0e230278",
  "name": "Bot Mr T - Production",
  "status": "stopped",
  "strategy_id": "uuid-estrategia"
}

# 2. Iniciar bot
POST /bot/start?bot_id=03008cda-1f72-4137-9d6b-279d0e230278
Authorization: Bearer eyJhbGc...

# 3. Verificar estado
GET /bot/status?bot_id=03008cda-1f72-4137-9d6b-279d0e230278
Authorization: Bearer eyJhbGc...

# 4. Detener bot
POST /bot/stop?bot_id=03008cda-1f72-4137-9d6b-279d0e230278
Authorization: Bearer eyJhbGc...
```

## Respuestas HTTP

La API utiliza códigos HTTP estándar:

- `200 OK` - Petición exitosa
- `201 Created` - Recurso creado exitosamente
- `400 Bad Request` - Datos inválidos
- `401 Unauthorized` - No autenticado o token inválido
- `404 Not Found` - Recurso no encontrado
- `500 Internal Server Error` - Error del servidor

## Notas importantes

1. **Tokens JWT**: Los tokens de acceso expiran después de cierto tiempo. Usa el refresh token para obtener nuevos tokens.

2. **Entornos**: 
   - `paper` - Trading con dinero virtual (recomendado para pruebas)
   - `live` - Trading con dinero real (usar con precaución)

3. **Rate limiting**: Alpaca tiene límites de requests. El bot está diseñado para respetarlos.

4. **CORS**: La API permite requests desde cualquier origen (`allow_origins=["*"]`). En producción, configura orígenes específicos.

## Soporte

Para más información sobre la estrategia de trading, consulta:
- `resources/estrategia_trainding.md` - Documentación detallada de la estrategia
- `resources/ddl.sql` - Estructura de la base de datos

---

**Versión**: 1.0.0  
**Licencia**: MIT
