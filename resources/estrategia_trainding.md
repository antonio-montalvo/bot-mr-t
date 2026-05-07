Una estrategia híbrida diseñada específicamente para automatización tiene muchas más probabilidades de sobrevivir que copiar literalmente un sistema discrecional.

La clave es separar el sistema en módulos:

```text id="w0f8r1"
1. Filtro de mercado
2. Filtro de liquidez
3. Detección de tendencia
4. Compresión de volatilidad
5. Confirmación institucional
6. Entrada
7. Gestión de riesgo
8. Gestión dinámica
9. Salida
```

Voy a proponerte una arquitectura profesional, pensada para:

* acciones US
* automatización total
* integración con Alpaca
* escalabilidad
* backtesting
* ejecución intradía o swing

---

# Estrategia híbrida automatizable

## Objetivo

Comprar acciones:

* líquidas
* fuertes
* institucionales
* en expansión de volatilidad
* con momentum real

Y cortar pérdidas rápido.

---

# 1. Filtro de mercado (Market Regime)

NO operar siempre.

Solo operar cuando el mercado general está sano.

## Condiciones

SPY:

* arriba EMA 50
* EMA 21 > EMA 50
* VIX debajo de 25
* QQQ fuerte relativo

## Regla

```text id="8jmk7y"
IF SPY > EMA50
AND EMA21 > EMA50
AND VIX < 25
THEN ENABLE_LONGS
ELSE CASH_MODE
```

Esto elimina muchísimo drawdown.

---

# 2. Filtro de liquidez

MUY importante para bots.

Evita:

* spreads grandes
* slippage
* traps

## Reglas

### Volumen promedio:

```text id="j9n0bh"
Average Daily Volume > 2M shares
```

### Dollar volume:

```text id="u7b9yb"
Price * Volume > 20M USD/day
```

### Spread:

```text id="g0t2z9"
BidAskSpread < 0.15%
```

### Precio mínimo:

```text id="p13xtv"
Price > 10 USD
```

---

# 3. Filtro de fuerza institucional

Inspirado en:

* JL Cava
* Jeff Cooper

## Reglas

### Relative Strength:

La acción debe rendir mejor que SPY.

```text id="j30pl3"
RS_20D > SPY_RS_20D
```

### Tendencia:

```text id="2ff3vc"
EMA20 > EMA50
EMA50 > EMA200
```

### Volumen:

```text id="j2uw0t"
CurrentVolume > 1.5x AvgVolume20
```

---

# 4. Setup principal (John Carter Squeeze)

Detectar compresión de volatilidad.

Usar:

* Bollinger Bands
* Keltner Channels

Condición squeeze:

\text{Squeeze ON: } BB \subset KC

## Confirmación momentum

Entrar SOLO cuando:

* momentum histogram cambia positivo
* vela rompe rango

---

# 5. Confirmación tipo Hoffman

Evitar fake breakouts.

## Confirmaciones:

* wick rejection
* breakout con volumen
* cierre arriba resistencia

---

# 6. Entrada

## Entrada Long

```text id="uok8v6"
IF:
- Market Regime = Bullish
- Liquidity OK
- Relative Strength Strong
- Squeeze Fired
- Breakout Confirmed
- Volume Spike

THEN:
BUY
```

---

# 7. Gestión de riesgo (MUY importante)

Aquí vive la rentabilidad real.

---

## Riesgo por operación

Nunca arriesgar más de:

```text id="4dr5s7"
0.5% - 1% del capital
```

Ejemplo:

* cuenta 100k
* riesgo máximo:

  * 500 USD

---

# 8. Stop Loss Inteligente

NO usar stops fijos.

Usar ATR dinámico.

StopLoss = EntryPrice - (1.5 \times ATR_{14})

---

# 9. Tamaño de posición

Fundamental para automatización.

PositionSize = \frac{RiskAmount}{Entry - StopLoss}

---

# 10. Gestión dinámica

## Parciales

```text id="y2j58z"
Take 50% at 2R
Move stop to breakeven
```

---

## Trailing stop

Usar:

* EMA 9
  o
* ATR trailing

---

# 11. Salidas

Salir cuando:

* momentum cae
* volumen desaparece
* cierre debajo EMA 9
* trailing stop activado

---

# 12. Protección de capital

MUY importante para bots.

## Daily Loss Limit

```text id="xw4crx"
IF DailyLoss > 3%
STOP TRADING TODAY
```

---

## Max Drawdown

```text id="7nk3ow"
IF Drawdown > 10%
Reduce Position Size 50%
```

---

# 13. Ranking de oportunidades

Score compuesto:

```text id="odupq8"
Score =
30% Relative Strength
25% Volume Expansion
20% Squeeze Strength
15% Trend Quality
10% Volatility Expansion
```

El bot compra SOLO top scores.

---

# Arquitectura recomendada

## Scanner Engine

Busca:

* liquidez
* squeezes
* momentum

---

## Signal Engine

Genera:

* buy/sell
* stop
* position size

---

## Risk Engine

Controla:

* drawdown
* exposición
* correlación

---

## Execution Engine

Manda órdenes:

* Alpaca
* Interactive Brokers
* Tradier

---

# Timeframes recomendados

## Swing:

* 4H
* Daily

Más estable.

---

## Intradía:

* 5m
* 15m

Más agresivo.

---

# Qué evitar

NO operar:

* penny stocks
* earnings
* spreads amplios
* baja liquidez
* premarket ilíquido

---

# KPIs importantes

Tu bot debe medir:

```text id="5n8kjg"
Win Rate
Profit Factor
Max Drawdown
Sharpe Ratio
Expectancy
Average R Multiple
```

---

# Resultado esperado REALISTA

Un sistema profesional bien ejecutado podría aspirar a:

```text id="1s86jo"
Win Rate: 45%-60%
Profit Factor: 1.5 - 2.5
Max DD: <15%
```

Eso ya es MUY bueno en trading real.

---

# Lo más importante

El edge NO viene solo del squeeze.

Viene de combinar:

* contexto
* liquidez
* volatilidad
* momentum
* gestión de riesgo
* filtrado institucional

Ahí es donde los bots empiezan a parecerse a sistemas profesionales reales.
