from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
import ccxt.async_support as ccxt  # LIBRERÍA PARA PRECIOS REALES
import statistics
import httpx
import datetime
import asyncio

# ======================================================
#        MCC Market Context API — Live Version v3.0
# ======================================================

app = FastAPI(title="MCC Market Context API", version="3.0.0 (Live + Coinglass)")

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
    ob_zones: List[ObZone] = []
    fvg_zones: List[FvgZone] = []
    micro_liquidity: List[LiquidityLevel] = []
    current_price: Optional[float] = None

class CoinglassLevels(BaseModel):
    N1: List[CoinglassCluster] = []
    N2: List[CoinglassCluster] = []
    N3: List[CoinglassCluster] = []

class CoinglassData(BaseModel):
    heatmap: CoinglassLevels
    liquidations: CoinglassLevels

class MccMarketContext(BaseModel):
    symbol: str
    session: str
    timeframes: Dict[str, TimeframeContext]
    coinglass: Optional[CoinglassData] = None


# ======================================================
#          CONEXIÓN A BINANCE (Precios Reales)
# ======================================================

exchange = ccxt.binance()

async def fetch_ohlcv(symbol: str, timeframe: str, lookback_bars: int):
    """
    Esta función va a buscar los precios REALES a Binance.
    """
    # Usamos await para no bloquear el programa mientras los datos bajan
    return await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback_bars)

def detect_structure_and_liquidity(ohlcv_1d, ohlcv_4h, ohlcv_1h, ohlcv_15m):
    """
    Analiza la estructura con los datos que bajamos de Binance.
    """
    # Precio actual real (última vela de 15m, cierre)
    latest_price = ohlcv_15m[-1][4] 
    
    # Estructura diaria
    swing_high = max(c[2] for c in ohlcv_1d) # Máximo real
    swing_low = min(c[3] for c in ohlcv_1d)  # Mínimo real
    midline = (swing_high + swing_low) / 2
    
    # Tendencia basada en media de 4H
    median_4h = statistics.median([c[4] for c in ohlcv_4h])
    trend_val = "bullish_HH_HL" if latest_price > median_4h else "bearish_LH_LL"
    bias = "discount_LONG" if latest_price < midline else "premium_SHORT"

    # Contexto 1D
    tf_1d = TimeframeContext(
        bias=bias, trend=trend_val, bos="up" if "bullish" in trend_val else "down",
        swing_high=swing_high, swing_low=swing_low, midline_50=midline, current_price=latest_price
    )
    
    # Contexto 4H
    tf_4h = TimeframeContext(
        bos="up" if "bullish" in trend_val else "down",
        ob_zones=[ObZone(type="bullish", from_=midline*0.98, to=midline*1.02, state="decisional")],
        fvg_zones=[FvgZone(from_=midline*1.01, to=midline*1.02, state="active")]
    )

    # Contexto 1H
    tf_1h = TimeframeContext(
        bos="up" if "bullish" in trend_val else "down",
        ob_zones=[ObZone(type="bullish", from_=latest_price*0.995, to=latest_price*1.005, state="fresh")],
        fvg_zones=[FvgZone(from_=latest_price*1.002, to=latest_price*1.004, state="valid")]
    )

    # Contexto 15m
    tf_15m = TimeframeContext(
        current_price=latest_price, bos="up" if "bullish" in trend_val else "down",
        micro_liquidity=[
            LiquidityLevel(type="EQH", price=latest_price*1.005),
            LiquidityLevel(type="EQL", price=latest_price*0.995)
        ]
    )
    return {"1D": tf_1d, "4H": tf_4h, "1H": tf_1h, "15m": tf_15m}

async def fetch_coinglass_clusters(symbol: str):
    """Obtiene datos de Coinglass si están disponibles."""
    symbol_cg = symbol.replace("/", "").upper()
    api_base = "https://open-api.coinglass.com/api/pro/v1"
    headers = {"accept": "application/json", "coinglassSecret": "DEMO"} # Reemplazar con Key real si tienes
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{api_base}/futures/liquidation_heatmap?symbol={symbol_cg}", headers=headers)
            data = r.json().get("data", []) if r.status_code == 200 else []
        except: data = []
    
    clusters = []
    if data:
        for i in data[:3]:
            try:
                clusters.append(CoinglassCluster(
                    side="short" if i.get("side")=="short" else "long",
                    price=float(i.get("price",0)), size_usd=float(i.get("size",0))
                ))
            except: pass
            
    return CoinglassData(
        heatmap=CoinglassLevels(N3=clusters),
        liquidations=CoinglassLevels(N3=[])
    )

def detect_session():
    h = datetime.datetime.utcnow().hour
    return "NY" if 12<=h<20 else "LDN" if 7<=h<12 else "ASIA"

@app.on_event("shutdown")
async def shutdown_event():
    await exchange.close()

# ======================================================
#                  ENDPOINT PRINCIPAL
# ======================================================

@app.get("/mcc/market-context", response_model=MccMarketContext)
async def get_market_context(
    symbol: str = Query("BTC/USDT"),
    timeframe: str = "1h",
    lookback_bars: int = 300,
    include_coinglass: bool = True
):
    # 1. Traemos velas REALES de Binance
    o1 = await fetch_ohlcv(symbol, "1d", lookback_bars)
    o4 = await fetch_ohlcv(symbol, "4h", lookback_bars)
    oh = await fetch_ohlcv(symbol, "1h", lookback_bars)
    o15 = await fetch_ohlcv(symbol, "15m", lookback_bars)
    
    # 2. Analizamos estructura
    ctx = detect_structure_and_liquidity(o1, o4, oh, o15)
    
    # 3. Traemos Coinglass
    cg = await fetch_coinglass_clusters(symbol) if include_coinglass else None
    
    return MccMarketContext(symbol=symbol, session=detect_session(), timeframes=ctx, coinglass=cg)