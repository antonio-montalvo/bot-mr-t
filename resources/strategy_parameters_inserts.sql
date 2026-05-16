-- ============================================================
-- INSERT de parámetros de estrategia por defecto
-- ============================================================
-- Ejecutar después de crear un bot con su estrategia
-- Reemplazar {strategy_id} con el UUID de la estrategia creada
-- ============================================================

-- ─── MARKET REGIME PARAMETERS ───────────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'market_regime.spy_symbol', 'SPY', 'str'),
('{strategy_id}', 'market_regime.qqq_symbol', 'QQQ', 'str'),
('{strategy_id}', 'market_regime.vix_symbol', 'VIXY', 'str'),
('{strategy_id}', 'market_regime.ema_fast', '21', 'int'),
('{strategy_id}', 'market_regime.ema_slow', '50', 'int'),
('{strategy_id}', 'market_regime.vix_max', '25.0', 'float');

-- ─── LIQUIDITY PARAMETERS ───────────────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'liquidity.min_avg_volume', '2000000', 'int'),
('{strategy_id}', 'liquidity.min_dollar_volume', '20000000.0', 'float'),
('{strategy_id}', 'liquidity.max_spread_pct', '0.0015', 'float'),
('{strategy_id}', 'liquidity.min_price', '10.0', 'float');

-- ─── INSTITUTIONAL STRENGTH PARAMETERS ──────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'institutional.rs_lookback_days', '20', 'int'),
('{strategy_id}', 'institutional.ema_short', '20', 'int'),
('{strategy_id}', 'institutional.ema_mid', '50', 'int'),
('{strategy_id}', 'institutional.ema_long', '200', 'int'),
('{strategy_id}', 'institutional.volume_spike_multiplier', '1.5', 'float');

-- ─── SQUEEZE DETECTION PARAMETERS ───────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'squeeze.bb_length', '20', 'int'),
('{strategy_id}', 'squeeze.bb_std', '2.0', 'float'),
('{strategy_id}', 'squeeze.kc_length', '20', 'int'),
('{strategy_id}', 'squeeze.kc_atr_multiplier', '1.5', 'float'),
('{strategy_id}', 'squeeze.momentum_length', '12', 'int');

-- ─── RISK MANAGEMENT PARAMETERS ─────────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'risk.max_risk_per_trade_pct', '0.01', 'float'),
('{strategy_id}', 'risk.atr_stop_multiplier', '1.5', 'float'),
('{strategy_id}', 'risk.atr_length', '14', 'int'),
('{strategy_id}', 'risk.take_profit_r_multiple', '2.0', 'float'),
('{strategy_id}', 'risk.trailing_ema', '9', 'int'),
('{strategy_id}', 'risk.daily_loss_limit_pct', '0.03', 'float'),
('{strategy_id}', 'risk.max_drawdown_pct', '0.10', 'float'),
('{strategy_id}', 'risk.max_open_positions', '5', 'int');

-- ─── SCORER PARAMETERS ──────────────────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'scorer.weight_relative_strength', '0.30', 'float'),
('{strategy_id}', 'scorer.weight_volume_expansion', '0.25', 'float'),
('{strategy_id}', 'scorer.weight_squeeze_strength', '0.20', 'float'),
('{strategy_id}', 'scorer.weight_trend_quality', '0.15', 'float'),
('{strategy_id}', 'scorer.weight_volatility_expansion', '0.10', 'float'),
('{strategy_id}', 'scorer.min_score', '0.6', 'float');

-- ─── BOT GENERAL PARAMETERS ─────────────────────────────────
INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type) VALUES
('{strategy_id}', 'timeframe', '1Day', 'str'),
('{strategy_id}', 'scan_interval_seconds', '60', 'int'),
('{strategy_id}', 'watchlist', 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,CRM,NFLX,ADBE,AVGO,COST,PEP,LLY,UNH,V,MA,JPM,HD', 'list');

-- ============================================================
-- EJEMPLO DE USO:
-- ============================================================
-- 1. Crear bot y estrategia:
--    INSERT INTO bot_instances (...) RETURNING id;
--    INSERT INTO strategies (bot_id, ...) RETURNING id;
--
-- 2. Copiar el strategy_id obtenido
--
-- 3. Reemplazar {strategy_id} en este archivo con el UUID real
--
-- 4. Ejecutar todos los INSERTs
--
-- 5. El bot cargará automáticamente estos parámetros usando:
--    BotConfig.from_database(db, strategy_id)
-- ============================================================

-- ============================================================
-- MODIFICAR PARÁMETROS INDIVIDUALES:
-- ============================================================
-- UPDATE strategy_parameters 
-- SET param_value = '30' 
-- WHERE strategy_id = '{strategy_id}' 
--   AND param_key = 'market_regime.ema_fast';
--
-- UPDATE strategy_parameters 
-- SET param_value = '0.02' 
-- WHERE strategy_id = '{strategy_id}' 
--   AND param_key = 'risk.max_risk_per_trade_pct';
-- ============================================================
