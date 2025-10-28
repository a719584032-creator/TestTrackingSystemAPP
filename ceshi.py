"""
双周期趋势通道突破策略（小时 + 15 分钟）——模板
- 主周期：1H
- 辅助周期：15m
- 动态止损：多头=上一根bar的高，空头=上一根bar的低
- 场景1：仅用1H信号开平仓
- 场景2：1H与15m信号一致才开仓（多周期共振）

策略中“通道计算（UP/DOWN）”留有钩子函数，你可以把图片里的精确公式
替换进去；默认给了一个“上一bar振幅/4”的近似实现（贴合你图里“/4”的思想）。
"""

import pandas as pd
import numpy as np
import yfinance as yf
import datetime as dt
from dataclasses import dataclass

# =========================
# 数据获取
# =========================
def fetch_yf(ticker: str, period="45d", interval="15m") -> pd.DataFrame:
    """
    从 yfinance 获取 K 线数据
    - 15m/1h 等分钟级数据通常只能获取近 ~60 天
    """
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False, threads=False)
    df = df.dropna()
    df = df.rename(
        columns={"Open":"open", "High":"high", "Low":"low", "Close":"close", "Volume":"volume"}
    )
    return df[["open","high","low","close","volume"]]

# =========================
# 通道计算（可替换为你的精确规则）
# =========================
def channel_by_prev_range_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """
    近似：以上一根bar的振幅/4 为通道半宽度（贴合“/4”的思路）
    UP   = 当前open + (上一bar high-low)/4
    DOWN = 当前open - (上一bar high-low)/4

    你可以在这里替换成：结合“本日开盘、昨高昨低”等更复杂的公式。
    """
    prev_range = (df["high"].shift(1) - df["low"].shift(1)).clip(lower=0)
    half_width = prev_range / 4.0
    out = pd.DataFrame(index=df.index)
    out["UP"] = df["open"] + half_width
    out["DOWN"] = df["open"] - half_width
    # 供“强势/弱势”确认用（上一根的高低）
    out["last_HW"] = df["high"].shift(1)
    out["last_LW"] = df["low"].shift(1)
    return out

# =========================
# 信号生成
# =========================
@dataclass
class SignalConfig:
    """开平仓阈值定义"""
    use_confirm: bool = False  # 场景2：是否需要 1H 与 15m 共振
    # 下面是占位，如果你想进一步增加过滤条件（如最小波动、量能），都可以加在这里

def gen_signals(df: pd.DataFrame, ch: pd.DataFrame) -> pd.DataFrame:
    """
    基于通道的开平仓信号（单周期版本）
    规则（来自你的图，按近似实现）：
    - 多头开仓：  close > UP 且 close > last_HW
    - 空头开仓：  close < DOWN 且 close < last_LW
    - 多头平仓：  close < STOPLOSS（多头STOPLOSS=上一bar高）
    - 空头平仓：  close > STOPLOSS（空头STOPLOSS=上一bar低）
    """
    sig = pd.DataFrame(index=df.index)
    sig["long_entry"]  = (df["close"] > ch["UP"])   & (df["close"] > ch["last_HW"])
    sig["short_entry"] = (df["close"] < ch["DOWN"]) & (df["close"] < ch["last_LW"])

    # 动态止损：用上一根bar的高/低
    sig["long_exit"]  = df["close"] < ch["last_LW"]  # 用上一低作多头止损（等价于触发反向弱势）
    sig["short_exit"] = df["close"] > ch["last_HW"]  # 用上一高作空头止损

    return sig

# =========================
# 多周期合成（1H 主 + 15m 辅）
# =========================
def resample_to_hour(df15: pd.DataFrame) -> pd.DataFrame:
    """15m 聚合为 1H（OHLCV）"""
    rule = '1H'
    o = df15["open"].resample(rule).first()
    h = df15["high"].resample(rule).max()
    l = df15["low"].resample(rule).min()
    c = df15["close"].resample(rule).last()
    v = df15["volume"].resample(rule).sum()
    out = pd.concat([o,h,l,c,v], axis=1)
    out.columns = ["open","high","low","close","volume"]
    out = out.dropna()
    return out

def combine_multiframe_signals(sig1h: pd.DataFrame, sig15: pd.DataFrame, cfg: SignalConfig) -> pd.DataFrame:
    """
    - 场景1（默认）：直接使用 1H 信号。
    - 场景2（cfg.use_confirm=True）：要求 1H 与 15m 同向才开仓。
    平仓仍按 1H 动态止损（更干净）。
    """
    out = sig1h.copy()
    if cfg.use_confirm:
        # 对齐到 1H：用 15m 的“当前小时内是否出现过同向信号”进行确认
        sig15_h = pd.DataFrame(index=sig1h.index)
        sig15_h["long_entry"]  = sig15["long_entry"].resample('1H').max().reindex(sig1h.index).fillna(False)
        sig15_h["short_entry"] = sig15["short_entry"].resample('1H').max().reindex(sig1h.index).fillna(False)
        out["long_entry"]  = sig1h["long_entry"]  & sig15_h["long_entry"]
        out["short_entry"] = sig1h["short_entry"] & sig15_h["short_entry"]
    return out

# =========================
# 回测引擎（简单版）
# =========================
@dataclass
class BTConfig:
    fee_bp: float = 3.0   # 手续费 基点（双边各一次），3bp=0.03%
    slip_bp: float = 2.0  # 滑点 基点
    allow_short: bool = True  # 是否允许做空
    risk_per_trade: float = 1.0  # 这里只做满仓/空仓示例，扩展位

def backtest(df1h: pd.DataFrame, sig: pd.DataFrame, cfg: BTConfig) -> pd.DataFrame:
    """
    以 1H 为交易时钟：
    - long_entry / short_entry 触发开仓
    - long_exit / short_exit   触发平仓
    不叠加仓位，仓位在 {-1,0,1} 之间切换。
    """
    fee = (cfg.fee_bp + cfg.slip_bp) / 1e4  # 成本合计
    pos = 0
    positions = []
    for i in range(len(df1h)):
        le = bool(sig["long_entry"].iloc[i])
        se = bool(sig["short_entry"].iloc[i])
        lx = bool(sig["long_exit"].iloc[i])
        sx = bool(sig["short_exit"].iloc[i])

        if pos == 0:
            if le:
                pos = 1
            elif se and cfg.allow_short:
                pos = -1
        elif pos == 1:
            if lx or se:   # 多头止损或反向信号
                pos = 0
        elif pos == -1:
            if sx or le:   # 空头止损或反向信号
                pos = 0
        positions.append(pos)

    bt = pd.DataFrame(index=df1h.index)
    bt["pos"] = positions
    bt["ret_raw"] = df1h["close"].pct_change().fillna(0.0)
    # 成本在换手时扣除
    turn = bt["pos"].diff().abs().fillna(0.0)
    bt["cost"] = turn * fee
    bt["ret"] = bt["pos"].shift(1).fillna(0) * bt["ret_raw"] - bt["cost"]
    bt["curve"] = (1 + bt["ret"]).cumprod()
    return bt

def perf_stats(curve: pd.Series, ret: pd.Series, freq_per_year=252*7):  # 1H 粗略年化：每天约7根有效bar
    if curve.empty:
        return {}
    years = len(curve)/freq_per_year
    cagr = curve.iloc[-1]**(1/max(years,1e-9)) - 1
    peak = curve.cummax()
    mdd = (curve/peak - 1).min()
    sharpe = np.sqrt(freq_per_year) * (ret.mean() / (ret.std() + 1e-12))
    return {"CAGR": cagr, "MDD": mdd, "Sharpe": sharpe}

# =========================
# 示例：AAPL（近 45 天）
# =========================
if __name__ == "__main__":
    ticker = "AAPL"
    print(f"Fetching {ticker} ...")
    df15 = fetch_yf(ticker, period="45d", interval="15m")
    df1h  = resample_to_hour(df15)

    # 计算通道
    ch15 = channel_by_prev_range_quarter(df15)
    ch1h  = channel_by_prev_range_quarter(df1h)

    # 生成信号
    sig15 = gen_signals(df15, ch15)
    sig1h  = gen_signals(df1h,  ch1h)

    # 场景1：仅 1H
    s1 = combine_multiframe_signals(sig1h, sig15, SignalConfig(use_confirm=False))
    bt1 = backtest(df1h, s1, BTConfig())
    stats1 = perf_stats(bt1["curve"], bt1["ret"])
    print("\n场景1（仅1H）绩效：", {k: round(v,4) for k,v in stats1.items()})

    # 场景2：1H 与 15m 共振确认
    s2 = combine_multiframe_signals(sig1h, sig15, SignalConfig(use_confirm=True))
    bt2 = backtest(df1h, s2, BTConfig())
    stats2 = perf_stats(bt2["curve"], bt2["ret"])
    print("场景2（共振）绩效：  ", {k: round(v,4) for k,v in stats2.items()})

    # 可视化（可选）
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10,4))
        plt.plot(bt1.index, bt1["curve"], label="Scenario1 1H only")
        plt.plot(bt2.index, bt2["curve"], label="Scenario2 1H+15m confirm")
        plt.title(f"{ticker} 双周期通道策略 - 资金曲线（近45天，yfinance）")
        plt.legend(); plt.tight_layout(); plt.show()
    except Exception as e:
        print("Plot skipped:", e)
