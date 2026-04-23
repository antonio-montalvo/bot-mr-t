# Bot Mr T

Este es un bot para hacer trading en la bolsa de valores con paper trading, conectado a **Alpaca Markets**.

## Estructura del proyecto

```
bot-mr-t/
├── app/
│   ├── auth/           # Autenticación con la API de Alpaca
│   ├── broker/         # Interfaz con el broker (datos de mercado, cuenta)
│   ├── strategy/       # Estrategias de trading (clase base abstracta)
│   ├── trading/        # Motor de ejecución del bot
│   ├── risk/           # Gestión de riesgo
│   ├── orders/         # Gestión de órdenes
│   ├── positions/      # Gestión de posiciones abiertas
│   ├── logs/           # Configuración de logging
│   ├── db/             # Persistencia con SQLite
│   └── main.py         # Punto de entrada
├── .env.example        # Variables de entorno de ejemplo
├── requirements.txt    # Dependencias
└── ReadMe.md
```

## Configuración

1. Crear un entorno virtual e instalar dependencias:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copiar `.env.example` a `.env` y configurar las API keys de Alpaca:
   ```bash
   copy .env.example .env
   ```

3. Ejecutar el bot:
   ```bash
   python -m app.main
   ```
