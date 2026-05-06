-- =============================================================
-- Bot Mr T – DDL (PostgreSQL)
-- =============================================================
-- Ejecutar contra la base de datos trading_bot.
-- Las tablas se crean con UUID como PK usando gen_random_uuid().
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── USERS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255),
    is_active     BOOLEAN   DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── API_KEYS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker_name          VARCHAR(50)  NOT NULL,
    environment          VARCHAR(20)  NOT NULL,
    api_key_encrypted    VARCHAR(500) NOT NULL,
    secret_key_encrypted VARCHAR(500) NOT NULL,
    is_active            BOOLEAN   DEFAULT TRUE,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── ASSETS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol     VARCHAR(20)  NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    asset_type VARCHAR(20)  NOT NULL,
    exchange   VARCHAR(50),
    is_active  BOOLEAN DEFAULT TRUE
);

-- ─── BOT_INSTANCES ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_instances (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         VARCHAR(100) NOT NULL,
    broker_name  VARCHAR(50)  NOT NULL,
    environment  VARCHAR(20)  NOT NULL,
    status       VARCHAR(20)  DEFAULT 'stopped',
    is_enabled   BOOLEAN      DEFAULT FALSE,
    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ─── STRATEGIES ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id      UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    type        VARCHAR(50)  NOT NULL,
    description TEXT,
    is_active   BOOLEAN   DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── STRATEGY_PARAMETERS ───────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id  UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    param_key    VARCHAR(100) NOT NULL,
    param_value  VARCHAR(500),
    data_type    VARCHAR(30),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── TRADING_SIGNALS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS trading_signals (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id  UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    asset_id     UUID NOT NULL REFERENCES assets(id),
    signal_type  VARCHAR(20)    NOT NULL,
    reason       VARCHAR(500),
    price        DECIMAL(18,8),
    confidence   DECIMAL(5,4),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── ORDERS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id           UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    asset_id         UUID NOT NULL REFERENCES assets(id),
    signal_id        UUID REFERENCES trading_signals(id),
    broker_order_id  VARCHAR(100),
    side             VARCHAR(10)    NOT NULL,
    order_type       VARCHAR(20)    NOT NULL,
    status           VARCHAR(20)    DEFAULT 'pending',
    quantity         DECIMAL(18,8)  NOT NULL,
    limit_price      DECIMAL(18,8),
    stop_price       DECIMAL(18,8),
    submitted_price  DECIMAL(18,8),
    submitted_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── EXECUTIONS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS executions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id             UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    broker_execution_id  VARCHAR(100),
    filled_quantity      DECIMAL(18,8) NOT NULL,
    filled_price         DECIMAL(18,8) NOT NULL,
    commission           DECIMAL(18,8) DEFAULT 0,
    executed_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── POSITIONS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id              UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    asset_id            UUID NOT NULL REFERENCES assets(id),
    quantity            DECIMAL(18,8)  NOT NULL DEFAULT 0,
    average_entry_price DECIMAL(18,8),
    current_price       DECIMAL(18,8),
    unrealized_pnl      DECIMAL(18,8)  DEFAULT 0,
    realized_pnl        DECIMAL(18,8)  DEFAULT 0,
    status              VARCHAR(20)    DEFAULT 'open',
    opened_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at           TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── BOT_RUNS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id        UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stopped_at    TIMESTAMP,
    status        VARCHAR(20) DEFAULT 'running',
    error_message TEXT
);

-- ─── BOT_COMMANDS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_commands (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id       UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    command      VARCHAR(50) NOT NULL,
    status       VARCHAR(20) DEFAULT 'pending',
    payload      JSON,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- ─── ACCOUNT_SNAPSHOTS ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS account_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id          UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    equity          DECIMAL(18,4) NOT NULL,
    cash            DECIMAL(18,4),
    buying_power    DECIMAL(18,4),
    portfolio_value DECIMAL(18,4),
    captured_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── RISK_EVENTS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id     UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    order_id   UUID REFERENCES orders(id),
    event_type VARCHAR(50) NOT NULL,
    severity   VARCHAR(20) NOT NULL,
    message    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── SYSTEM_LOGS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS system_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id     UUID NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
    level      VARCHAR(10) NOT NULL,
    module     VARCHAR(100),
    message    TEXT NOT NULL,
    context    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── MARKET_CANDLES ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_candles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id    UUID NOT NULL REFERENCES assets(id),
    timeframe   VARCHAR(10) NOT NULL,
    candle_time TIMESTAMP   NOT NULL,
    open        DECIMAL(18,8) NOT NULL,
    high        DECIMAL(18,8) NOT NULL,
    low         DECIMAL(18,8) NOT NULL,
    close       DECIMAL(18,8) NOT NULL,
    volume      BIGINT        DEFAULT 0,
    UNIQUE (asset_id, timeframe, candle_time)
);

-- ─── ACCOUNT_CURRENT_STATE ─────────────────────────────────
CREATE TABLE account_current_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    bot_id UUID NOT NULL UNIQUE,

    broker_name VARCHAR(50) NOT NULL,
    environment VARCHAR(20) NOT NULL,

    account_id VARCHAR(100),

    equity NUMERIC(18,2) NOT NULL DEFAULT 0,
    cash NUMERIC(18,2) NOT NULL DEFAULT 0,
    buying_power NUMERIC(18,2) NOT NULL DEFAULT 0,
    portfolio_value NUMERIC(18,2) NOT NULL DEFAULT 0,

    currency VARCHAR(10) NOT NULL DEFAULT 'USD',

    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    trading_blocked BOOLEAN NOT NULL DEFAULT FALSE,

    last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_account_current_state_bot
        FOREIGN KEY (bot_id)
        REFERENCES bot_instances(id)
        ON DELETE CASCADE
);

-- ─── ÍNDICES ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_api_keys_user        ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_instances_user    ON bot_instances(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_bot        ON strategies(bot_id);
CREATE INDEX IF NOT EXISTS idx_strategy_params_strat ON strategy_parameters(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trading_signals_strat ON trading_signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_orders_bot            ON orders(bot_id);
CREATE INDEX IF NOT EXISTS idx_orders_asset          ON orders(asset_id);
CREATE INDEX IF NOT EXISTS idx_executions_order      ON executions(order_id);
CREATE INDEX IF NOT EXISTS idx_positions_bot         ON positions(bot_id);
CREATE INDEX IF NOT EXISTS idx_positions_asset       ON positions(asset_id);
CREATE INDEX IF NOT EXISTS idx_bot_runs_bot          ON bot_runs(bot_id);
CREATE INDEX IF NOT EXISTS idx_bot_commands_bot      ON bot_commands(bot_id);
CREATE INDEX IF NOT EXISTS idx_account_snap_bot      ON account_snapshots(bot_id);
CREATE INDEX IF NOT EXISTS idx_risk_events_bot       ON risk_events(bot_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_bot       ON system_logs(bot_id);
CREATE INDEX IF NOT EXISTS idx_market_candles_asset  ON market_candles(asset_id);
CREATE INDEX IF NOT EXISTS idx_account_current_state_bot_id    ON account_current_state(bot_id);
CREATE INDEX IF NOT EXISTS idx_account_current_state_last_synced ON account_current_state(last_synced_at);
