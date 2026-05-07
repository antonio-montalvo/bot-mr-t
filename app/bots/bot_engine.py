"""
Motor principal del bot de trading.

Ciclo de ejecución:
1. Verificar market regime
2. Escanear candidatos
3. Generar señales (squeeze + breakout)
4. Validar riesgo
5. Ejecutar órdenes
6. Gestionar posiciones abiertas (trailing stop, parciales)
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient

from app.db import Database
from app.bots.config import BotConfig
from app.bots.market_filter import MarketFilter
from app.bots.scanner import Scanner
from app.bots.signal_generator import SignalGenerator
from app.bots.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class BotEngine:
    """Motor de trading que ejecuta la estrategia híbrida."""

    def __init__(
        self,
        bot_id: str,
        trading_client: TradingClient,
        data_client: StockHistoricalDataClient,
        db: Database,
        config: Optional[BotConfig] = None,
    ):
        self.bot_id = bot_id
        self.trading_client = trading_client
        self.data_client = data_client
        self.db = db
        self.config = config or BotConfig()

        # Componentes de la estrategia
        self.market_filter = MarketFilter(data_client, self.config.market_regime)
        self.scanner = Scanner(
            data_client,
            self.config.liquidity,
            self.config.institutional,
            self.config.scorer,
        )
        self.signal_generator = SignalGenerator(data_client, self.config.squeeze)
        self.risk_manager = RiskManager(self.config.risk, db, bot_id)

        # Estado del engine
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._started_at: Optional[datetime] = None

    # ─── Control ─────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    def start(self):
        """Inicia el bot en un hilo background."""
        if self._running:
            return

        self._running = True
        self._started_at = datetime.now(timezone.utc)
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._update_bot_status("running")
        self._record_bot_run_start()
        self._log("INFO", "bot_engine", "Bot iniciado")
        logger.info("BotEngine %s iniciado", self.bot_id)

    def stop(self):
        """Detiene el bot."""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        self._update_bot_status("stopped")
        self._record_bot_run_stop()
        self._log("INFO", "bot_engine", "Bot detenido")
        self._started_at = None
        logger.info("BotEngine %s detenido", self.bot_id)

    # ─── Loop principal ──────────────────────────────────────────────────

    def _run_loop(self):
        """Loop principal del bot."""
        while self._running:
            try:
                self._cycle()
            except Exception as e:
                self._log("ERROR", "bot_engine", f"Error en ciclo: {e}")
                logger.exception("Error en ciclo del bot %s: %s", self.bot_id, e)

            # Esperar antes del siguiente ciclo
            for _ in range(self.config.scan_interval_seconds):
                if not self._running:
                    break
                time.sleep(1)

    def _cycle(self):
        """Un ciclo completo de la estrategia."""
        self._log("INFO", "cycle", "=== Iniciando ciclo de estrategia ===")
        
        # 1. Verificar si el mercado está abierto
        try:
            clock = self.trading_client.get_clock()
            if not clock.is_open:
                self._log("INFO", "market_check", "Mercado CERRADO - esperando apertura")
                logger.debug("Mercado cerrado, esperando...")
                return
            self._log("INFO", "market_check", "Mercado ABIERTO - continuando")
        except Exception as e:
            self._log("ERROR", "bot_engine", f"Error verificando clock: {e}")
            return

        # 2. Market Regime Filter
        self._log("INFO", "market_regime", "Evaluando régimen de mercado...")
        if not self.market_filter.is_bullish():
            self._log("WARNING", "market_regime", "Market regime: CASH MODE - no operar nuevas posiciones")
            # Gestionar posiciones existentes (trailing stops)
            self._manage_open_positions()
            return
        self._log("INFO", "market_regime", "Market regime: BULLISH - OK para operar")

        # 3. Verificar si podemos abrir nuevas posiciones
        self._log("INFO", "risk_check", "Verificando límites de riesgo...")
        if not self.risk_manager.can_trade():
            self._log("WARNING", "risk_check", "Límites de riesgo alcanzados - no abrir nuevas posiciones")
            self._manage_open_positions()
            return
        self._log("INFO", "risk_check", "Límites de riesgo OK - puede operar")

        # 4. Escanear candidatos
        self._log("INFO", "scanner", f"Escaneando watchlist ({len(self.config.watchlist)} símbolos)...")
        candidates = self.scanner.scan(self.config.watchlist)
        if not candidates:
            self._log("INFO", "scanner", "No se encontraron candidatos válidos")
            self._manage_open_positions()
            return

        self._log("INFO", "scanner", f"✓ Candidatos encontrados: {len(candidates)} - Top: {[c.symbol for c in candidates[:5]]}")
        self._log("INFO", "scanner", f"Scores: {[(c.symbol, round(c.total_score, 2)) for c in candidates[:5]]}")

        # 5. Generar señales para los top candidatos
        self._log("INFO", "signal_gen", "Evaluando señales para top 5 candidatos...")
        for idx, candidate in enumerate(candidates[:5], 1):  # Evaluar top 5
            if not self._running:
                break

            self._log("INFO", "signal_gen", f"[{idx}/5] Evaluando {candidate.symbol}...")
            signal = self.signal_generator.evaluate(candidate.symbol)

            if signal.is_valid and signal.entry_price > 0:
                self._log("INFO", "signal_gen", f"✓ Señal VÁLIDA para {signal.symbol} - Entry: ${signal.entry_price:.2f}, ATR: {signal.atr:.2f}")
                # 6. Verificar riesgo y ejecutar
                self._execute_entry(signal)

                # Re-verificar si podemos seguir operando
                if not self.risk_manager.can_trade():
                    self._log("INFO", "risk_check", "Límites alcanzados después de entrada - deteniendo búsqueda")
                    break
            else:
                self._log("INFO", "signal_gen", f"✗ Señal NO válida para {candidate.symbol}")

        # 7. Gestionar posiciones abiertas
        self._log("INFO", "position_mgmt", "Gestionando posiciones abiertas...")
        self._manage_open_positions()
        self._log("INFO", "cycle", "=== Ciclo completado ===")

    # ─── Ejecución de entrada ────────────────────────────────────────────

    def _execute_entry(self, signal):
        """Ejecuta una entrada basada en la señal."""
        try:
            self._log("INFO", "execution", f"Preparando entrada para {signal.symbol}...")
            
            # Obtener equity actual
            account = self.trading_client.get_account()
            equity = float(account.equity)
            self._log("INFO", "execution", f"Equity actual: ${equity:,.2f}")

            # Calcular position size
            qty = self.risk_manager.calculate_position_size(
                equity, signal.entry_price, signal.atr
            )

            if qty <= 0:
                self._log("WARNING", "execution", f"Position size = 0 para {signal.symbol}, skip")
                logger.debug("Position size = 0 para %s, skip", signal.symbol)
                return

            # Verificar que no tengamos ya posición en este símbolo
            if self._has_open_position(signal.symbol):
                self._log("WARNING", "execution", f"Ya existe posición abierta en {signal.symbol}, skip")
                return
            
            self._log("INFO", "execution", f"Position size calculado: {qty} acciones")

            # Calcular stops
            stop_loss = self.risk_manager.calculate_stop_loss(signal.entry_price, signal.atr)
            take_profit = self.risk_manager.calculate_take_profit(signal.entry_price, stop_loss)
            self._log("INFO", "execution", f"Stops calculados - SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}")

            # Enviar orden market
            self._log("INFO", "execution", f"Enviando orden MARKET BUY {signal.symbol} x{qty}...")
            order_request = MarketOrderRequest(
                symbol=signal.symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )

            order = self.trading_client.submit_order(order_request)
            self._log("INFO", "execution", f"✓ Orden enviada - Order ID: {order.id}")

            # Registrar en DB
            self._record_order(signal, order, qty, stop_loss, take_profit)
            self._record_signal(signal)

            self._log(
                "INFO", "execution",
                f"COMPRA: {signal.symbol} x{qty} @ ~{signal.entry_price:.2f} | "
                f"SL={stop_loss:.2f} TP={take_profit:.2f}"
            )

        except Exception as e:
            self._log("ERROR", "execution", f"Error ejecutando entrada {signal.symbol}: {e}")
            logger.exception("Error en ejecución para %s", signal.symbol)

    # ─── Gestión de posiciones ───────────────────────────────────────────

    def _manage_open_positions(self):
        """Gestiona trailing stops y salidas para posiciones abiertas."""
        try:
            positions = self.trading_client.get_all_positions()
            
            if not positions:
                self._log("INFO", "position_mgmt", "No hay posiciones abiertas")
                return
            
            self._log("INFO", "position_mgmt", f"Revisando {len(positions)} posición(es) abierta(s)")
            for pos in positions:
                unrealized_pnl = float(pos.unrealized_pl)
                unrealized_pnl_pct = float(pos.unrealized_plpc) * 100
                self._log("INFO", "position_mgmt", 
                         f"{pos.symbol}: Qty={pos.qty}, Entry=${pos.avg_entry_price}, "
                         f"Current=${pos.current_price}, PnL={unrealized_pnl_pct:.2f}%")
                self._check_exit_conditions(pos)

        except Exception as e:
            self._log("ERROR", "position_mgmt", f"Error gestionando posiciones: {e}")
            logger.debug("Error gestionando posiciones: %s", e)

    def _check_exit_conditions(self, position):
        """Verifica condiciones de salida para una posición."""
        symbol = position.symbol
        current_price = float(position.current_price)
        avg_entry = float(position.avg_entry_price)
        qty = abs(float(position.qty))

        # Buscar info de la orden original en DB
        cursor = self.db.conn.cursor()
        cursor.execute(
            """SELECT stop_price, limit_price FROM orders
               WHERE bot_id = %s AND broker_order_id IS NOT NULL
                 AND status = 'filled'
               ORDER BY submitted_at DESC LIMIT 1""",
            (self.bot_id,),
        )
        # Usar ATR-based trailing stop simplificado
        # Si el precio cayó por debajo del entry - 1.5*ATR, cerrar
        # Para MVP, usamos un trailing basado en % simple
        unrealized_pnl_pct = (current_price - avg_entry) / avg_entry if avg_entry > 0 else 0

        # Salida por stop loss (pérdida > 2%)
        if unrealized_pnl_pct < -0.02:
            self._close_position(symbol, qty, "stop_loss")
            return

        # Take partial at 2R (ganancia > 4%)
        if unrealized_pnl_pct > 0.04 and qty > 1:
            partial_qty = int(qty * 0.5)
            if partial_qty > 0:
                self._close_position(symbol, partial_qty, "take_partial_2R")
                return

        # Trailing stop: si ganó > 2% y ahora retrocede a 1%
        if unrealized_pnl_pct > 0.01 and unrealized_pnl_pct < 0.015:
            self._close_position(symbol, qty, "trailing_stop")

    def _close_position(self, symbol: str, qty: int, reason: str):
        """Cierra una posición (total o parcial)."""
        try:
            self._log("INFO", "execution", f"Cerrando posición {symbol} x{qty} - Razón: {reason}")
            order_request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading_client.submit_order(order_request)
            self._log("INFO", "execution", f"✓ VENTA ejecutada: {symbol} x{qty} | Razón: {reason} | Order ID: {order.id}")
        except Exception as e:
            self._log("ERROR", "execution", f"Error cerrando {symbol}: {e}")

    def _has_open_position(self, symbol: str) -> bool:
        """Verifica si ya tenemos posición abierta en este símbolo."""
        try:
            self.trading_client.get_open_position(symbol)
            return True
        except Exception:
            return False

    # ─── Registro en DB ──────────────────────────────────────────────────

    def _record_order(self, signal, order, qty: int, stop_loss: float, take_profit: float):
        """Registra la orden en la base de datos."""
        try:
            cursor = self.db.conn.cursor()

            # Asegurar que el asset existe
            cursor.execute("SELECT id FROM assets WHERE symbol = %s", (signal.symbol,))
            asset_row = cursor.fetchone()
            if not asset_row:
                cursor.execute(
                    "INSERT INTO assets (symbol, name, asset_type) VALUES (%s, %s, 'us_equity') RETURNING id",
                    (signal.symbol, signal.symbol),
                )
                asset_id = cursor.fetchone()[0]
            else:
                asset_id = asset_row[0]

            cursor.execute(
                """INSERT INTO orders
                   (bot_id, asset_id, broker_order_id, side, order_type,
                    status, quantity, stop_price, limit_price, submitted_at)
                   VALUES (%s, %s, %s, 'buy', 'market', 'submitted', %s, %s, %s, %s)""",
                (
                    self.bot_id, asset_id, str(order.id),
                    qty, stop_loss, take_profit,
                    datetime.now(timezone.utc),
                ),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error("Error registrando orden: %s", e)

    def _record_signal(self, signal):
        """Registra la señal de trading en la base de datos."""
        try:
            cursor = self.db.conn.cursor()

            cursor.execute("SELECT id FROM assets WHERE symbol = %s", (signal.symbol,))
            asset_row = cursor.fetchone()
            if not asset_row:
                return

            # Buscar estrategia activa del bot
            cursor.execute(
                "SELECT id FROM strategies WHERE bot_id = %s AND is_active = TRUE LIMIT 1",
                (self.bot_id,),
            )
            strat_row = cursor.fetchone()
            if not strat_row:
                return

            cursor.execute(
                """INSERT INTO trading_signals
                   (strategy_id, asset_id, signal_type, reason, price, confidence)
                   VALUES (%s, %s, 'buy', %s, %s, %s)""",
                (
                    strat_row[0], asset_row[0],
                    f"squeeze_fired={signal.squeeze_fired}, momentum={signal.momentum_positive}, breakout={signal.breakout_confirmed}",
                    signal.entry_price,
                    0.8,
                ),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error("Error registrando señal: %s", e)

    def _update_bot_status(self, status: str):
        """Actualiza el estado del bot en bot_instances."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE bot_instances SET status = %s, updated_at = %s WHERE id = %s",
                (status, datetime.now(timezone.utc), self.bot_id),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error("Error actualizando status del bot: %s", e)

    def _record_bot_run_start(self):
        """Registra inicio de ejecución en bot_runs."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "INSERT INTO bot_runs (bot_id, status) VALUES (%s, 'running')",
                (self.bot_id,),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error("Error registrando bot_run start: %s", e)

    def _record_bot_run_stop(self):
        """Registra detención en bot_runs."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """UPDATE bot_runs SET stopped_at = %s, status = 'stopped'
                   WHERE bot_id = %s AND status = 'running'
                   ORDER BY started_at DESC LIMIT 1""",
                (datetime.now(timezone.utc), self.bot_id),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.error("Error registrando bot_run stop: %s", e)

    def _log(self, level: str, module: str, message: str):
        """Escribe log en system_logs."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "INSERT INTO system_logs (bot_id, level, module, message) VALUES (%s, %s, %s, %s)",
                (self.bot_id, level, module, message),
            )
            self.db.conn.commit()
        except Exception:
            pass
