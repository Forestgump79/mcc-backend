from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import ccxt.async_support as ccxt
import statistics
import httpx
import datetime
from fastapi.responses import FileResponse

# ======================================================
#        MCC Market Context API — Live + Backtesting
# ======================================================

app = FastAPI(title="MCC Market Context API", version="3.1.0 (Live + Signals + Backtest)")


# ---------- MODELOS DE DATOS ----------

class ObZone(BaseModel):
    type: str
    from_: float
    to: float
    state: str


class FvgZone(BaseModel):
    from_: float
    to: float
    state: str


class LiquidityLevel(BaseModel):
    type: str
    price: float


class CoinglassCluster(BaseModel):
    side: str
    price: float
    size_usd: float


class TimeframeContext(BaseModel):
    bias: Optional[str] = None
    trend: Optional[str] = None
    bos: Optional[str] = None
    swing_high: Optional[float] = None
    swing_low: Optional[float] = None
    midline_50: Optional[float] = None
    ob_zones: List[ObZone] = Field(default_factory=list)
    fvg_zones: List[FvgZone] = Field(default_factory=list)
    micro_liquidity: List[LiquidityLevel] = Field(default_factory=list)
    current_price: Optional[float] = None


class CoinglassLevels(BaseModel):
    N1: List[CoinglassCluster] = Field(default_factory=list)
    N2: List[CoinglassCluster] = Field(default_factory=list)
    N3: List[CoinglassCluster] = Field(default_factory=list)


class CoinglassData(BaseModel):
    heatmap: CoinglassLevels
    liquidations: CoinglassLevels


class MccMarketContext(BaseModel):
    symbol: str
    session: str
    timeframes: Dict[str, TimeframeContext]
    coinglass: Optional[CoinglassData] = None


class SignalSuggestion(BaseModel):
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float


class SignalResponse(BaseModel):
    symbol: str
    timeframe: str
    current_price: float
    bias: str
    trend: str
    suggestion: SignalSuggestion


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTC/USDT")
    timeframe: str = Field(default="1h")
    lookback_bars: int = Field(default=500, ge=120, le=3000)
    fast_period: int = Field(default=20, ge=2, le=200)
    slow_period: int = Field(default=50, ge=5, le=400)
    fee_bps: float = Field(default=4.0, ge=0, le=100)


class BacktestTrade(BaseModel):
    side: str
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    return_pct: float


class BacktestMetrics(BaseModel):
    total_return_pct: float
    buy_and_hold_return_pct: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    trades: int


class BacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    fee_bps: float
    metrics: BacktestMetrics
    recent_trades: List[BacktestTrade]


# ======================================================
#          CONEXIÓN A BINANCE (Precios Reales)
# ======================================================

exchange = ccxt.binance()


async def fetch_ohlcv(symbol: str, timeframe: str, lookback_bars: int):
    return await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback_bars)


async def safe_fetch_ohlcv(symbol: str, timeframe: str, lookback_bars: int):
    try:
        data = await fetch_ohlcv(symbol, timeframe, lookback_bars)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudieron obtener velas de Binance ({timeframe}): {exc}") from exc

    if not data:
        raise HTTPException(status_code=502, detail=f"Binance devolvió datos vacíos para {symbol} {timeframe}")
    return data


def detect_structure_and_liquidity(ohlcv_1d, ohlcv_4h, ohlcv_1h, ohlcv_15m):
    latest_price = ohlcv_15m[-1][4]

    swing_high = max(c[2] for c in ohlcv_1d)
    swing_low = min(c[3] for c in ohlcv_1d)
    midline = (swing_high + swing_low) / 2

    median_4h = statistics.median([c[4] for c in ohlcv_4h])
    trend_val = "bullish_HH_HL" if latest_price > median_4h else "bearish_LH_LL"
    bias = "discount_LONG" if latest_price < midline else "premium_SHORT"

    tf_1d = TimeframeContext(
        bias=bias,
        trend=trend_val,
        bos="up" if "bullish" in trend_val else "down",
        swing_high=swing_high,
        swing_low=swing_low,
        midline_50=midline,
        current_price=latest_price,
    )

    tf_4h = TimeframeContext(
        bos="up" if "bullish" in trend_val else "down",
        ob_zones=[ObZone(type="bullish", from_=midline * 0.98, to=midline * 1.02, state="decisional")],
        fvg_zones=[FvgZone(from_=midline * 1.01, to=midline * 1.02, state="active")],
    )

    tf_1h = TimeframeContext(
        bos="up" if "bullish" in trend_val else "down",
        ob_zones=[ObZone(type="bullish", from_=latest_price * 0.995, to=latest_price * 1.005, state="fresh")],
        fvg_zones=[FvgZone(from_=latest_price * 1.002, to=latest_price * 1.004, state="valid")],
    )

    tf_15m = TimeframeContext(
        current_price=latest_price,
        bos="up" if "bullish" in trend_val else "down",
        micro_liquidity=[
            LiquidityLevel(type="EQH", price=latest_price * 1.005),
            LiquidityLevel(type="EQL", price=latest_price * 0.995),
        ],
    )
    return {"1D": tf_1d, "4H": tf_4h, "1H": tf_1h, "15m": tf_15m}


async def fetch_coinglass_clusters(symbol: str):
    symbol_cg = symbol.replace("/", "").upper()
    api_base = "https://open-api.coinglass.com/api/pro/v1"
    headers = {"accept": "application/json", "coinglassSecret": "DEMO"}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{api_base}/futures/liquidation_heatmap?symbol={symbol_cg}", headers=headers)
            data = r.json().get("data", []) if r.status_code == 200 else []
        except Exception:
            data = []

    clusters = []
    if data:
        for i in data[:3]:
            try:
                clusters.append(
                    CoinglassCluster(
                        side="short" if i.get("side") == "short" else "long",
                        price=float(i.get("price", 0)),
                        size_usd=float(i.get("size", 0)),
                    )
                )
            except (TypeError, ValueError):
                pass

    return CoinglassData(heatmap=CoinglassLevels(N3=clusters), liquidations=CoinglassLevels(N3=[]))


def detect_session():
    h = datetime.datetime.utcnow().hour
    return "NY" if 12 <= h < 20 else "LDN" if 7 <= h < 12 else "ASIA"


def simple_moving_average(values: List[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    rolling_sum = sum(values[:period])
    out[period - 1] = rolling_sum / period
    for i in range(period, len(values)):
        rolling_sum += values[i] - values[i - period]
        out[i] = rolling_sum / period
    return out


def build_signal(current_price: float, trend: str) -> SignalSuggestion:
    if "bullish" in trend:
        entry = current_price
        stop = current_price * 0.99
        tp = current_price * 1.02
        rr = (tp - entry) / (entry - stop)
        return SignalSuggestion(side="long", entry=entry, stop_loss=stop, take_profit=tp, risk_reward=round(rr, 2))

    entry = current_price
    stop = current_price * 1.01
    tp = current_price * 0.98
    rr = (entry - tp) / (stop - entry)
    return SignalSuggestion(side="short", entry=entry, stop_loss=stop, take_profit=tp, risk_reward=round(rr, 2))


def run_sma_backtest(ohlcv: List[List[float]], fast_period: int, slow_period: int, fee_bps: float):
    closes = [c[4] for c in ohlcv]
    times = [int(c[0]) for c in ohlcv]
    fee_pct = fee_bps / 10000.0

    fast = simple_moving_average(closes, fast_period)
    slow = simple_moving_average(closes, slow_period)

    position_open = False
    entry_price = 0.0
    entry_time = 0
    trades = []
    equity_curve = [1.0]
    equity = 1.0

    for i in range(1, len(closes)):
        if fast[i] is None or slow[i] is None or fast[i - 1] is None or slow[i - 1] is None:
            equity_curve.append(equity)
            continue

        cross_up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
        cross_down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]

        if not position_open and cross_up:
            position_open = True
            entry_price = closes[i]
            entry_time = times[i]
        elif position_open and cross_down:
            exit_price = closes[i]
            gross_ret = (exit_price - entry_price) / entry_price
            net_ret = gross_ret - (2 * fee_pct)
            equity *= 1 + net_ret
            trades.append(
                BacktestTrade(
                    side="long",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=times[i],
                    exit_price=exit_price,
                    return_pct=round(net_ret * 100, 4),
                )
            )
            position_open = False
        equity_curve.append(equity)

    if position_open:
        exit_price = closes[-1]
        gross_ret = (exit_price - entry_price) / entry_price
        net_ret = gross_ret - (2 * fee_pct)
        equity *= 1 + net_ret
        trades.append(
            BacktestTrade(
                side="long",
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=times[-1],
                exit_price=exit_price,
                return_pct=round(net_ret * 100, 4),
            )
        )
        equity_curve[-1] = equity

    winning = [t for t in trades if t.return_pct > 0]
    losing = [t for t in trades if t.return_pct <= 0]

    gross_profit = sum(t.return_pct for t in winning)
    gross_loss = abs(sum(t.return_pct for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    peak = equity_curve[0]
    max_dd = 0.0
    for point in equity_curve:
        peak = max(peak, point)
        dd = (peak - point) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    total_return = (equity - 1.0) * 100
    buy_hold = ((closes[-1] / closes[0]) - 1.0) * 100
    win_rate = (len(winning) / len(trades) * 100) if trades else 0.0

    metrics = BacktestMetrics(
        total_return_pct=round(total_return, 4),
        buy_and_hold_return_pct=round(buy_hold, 4),
        win_rate_pct=round(win_rate, 2),
        profit_factor=round(profit_factor, 4),
        max_drawdown_pct=round(max_dd * 100, 4),
        trades=len(trades),
    )
    return metrics, trades[-10:]


@app.on_event("shutdown")
async def shutdown_event():
    await exchange.close()


# ======================================================
#                        ENDPOINTS
# ======================================================

@app.get("/mcc/market-context", response_model=MccMarketContext)
async def get_market_context(
    symbol: str = Query("BTC/USDT"),
    timeframe: str = "1h",
    lookback_bars: int = 300,
    include_coinglass: bool = True,
):
    o1 = await safe_fetch_ohlcv(symbol, "1d", lookback_bars)
    o4 = await safe_fetch_ohlcv(symbol, "4h", lookback_bars)
    oh = await safe_fetch_ohlcv(symbol, "1h", lookback_bars)
    o15 = await safe_fetch_ohlcv(symbol, "15m", lookback_bars)

    ctx = detect_structure_and_liquidity(o1, o4, oh, o15)
    cg = await fetch_coinglass_clusters(symbol) if include_coinglass else None

    return MccMarketContext(symbol=symbol, session=detect_session(), timeframes=ctx, coinglass=cg)


@app.get("/mcc/signals", response_model=SignalResponse)
async def get_signal_suggestion(
    symbol: str = Query("BTC/USDT"),
    timeframe: str = Query("1h"),
    lookback_bars: int = Query(300, ge=120, le=2000),
):
    o1 = await safe_fetch_ohlcv(symbol, "1d", lookback_bars)
    o4 = await safe_fetch_ohlcv(symbol, "4h", lookback_bars)
    oh = await safe_fetch_ohlcv(symbol, "1h", lookback_bars)
    o15 = await safe_fetch_ohlcv(symbol, "15m", lookback_bars)
    ctx = detect_structure_and_liquidity(o1, o4, oh, o15)

    trend = ctx["1D"].trend or "bearish_LH_LL"
    bias = ctx["1D"].bias or "premium_SHORT"
    current_price = ctx["15m"].current_price or o15[-1][4]

    return SignalResponse(
        symbol=symbol,
        timeframe=timeframe,
        current_price=current_price,
        bias=bias,
        trend=trend,
        suggestion=build_signal(current_price, trend),
    )


@app.post("/mcc/backtest", response_model=BacktestResponse)
async def run_backtest(payload: BacktestRequest):
    if payload.fast_period >= payload.slow_period:
        raise HTTPException(status_code=400, detail="fast_period debe ser menor que slow_period")

    ohlcv = await safe_fetch_ohlcv(payload.symbol, payload.timeframe, payload.lookback_bars)
    metrics, recent_trades = run_sma_backtest(
        ohlcv=ohlcv,
        fast_period=payload.fast_period,
        slow_period=payload.slow_period,
        fee_bps=payload.fee_bps,
    )

    return BacktestResponse(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        fast_period=payload.fast_period,
        slow_period=payload.slow_period,
        fee_bps=payload.fee_bps,
        metrics=metrics,
        recent_trades=recent_trades,
    )


@app.get("/health")
async def healthcheck():
    return {"status": "ok", "service": app.title, "version": app.version}


@app.get("/", response_class=FileResponse)
async def frontend_home():
    return FileResponse("frontend/index.html")
