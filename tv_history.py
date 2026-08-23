#!/usr/bin/env python3
r"""Minimal TradingView daily-OHLCV history client (unofficial websocket API).

Anonymous access, no login. One connection per symbol; ~0.5s pause between
symbols keeps us under the throttle. Returns a DataFrame indexed by date with
columns Open/High/Low/Close/Volume.

Usage:
    from tv_history import tv_daily
    df = tv_daily("RELIANCE", "NSE", n_bars=5000)
"""

import json
import random
import re
import time

import pandas as pd
from websocket import create_connection

WS_URL = "wss://data.tradingview.com/socket.io/websocket?origin=www.tradingview.com"


def _rand_id(prefix: str) -> str:
    return prefix + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=12))


def _pack(msg: str) -> str:
    return f"~m~{len(msg)}~m~{msg}"


def _frames(raw: str):
    for part in raw.split("~m~"):
        if part.isdigit() or not part:
            continue
        yield part


def _send(ws, obj) -> None:
    ws.send(_pack(json.dumps(obj)))


def tv_daily(symbol: str, exchange: str = "NSE", n_bars: int = 5000,
             timeout_s: int = 45) -> pd.DataFrame | None:
    try:
        ws = create_connection(WS_URL, timeout=timeout_s,
                               origin="https://www.tradingview.com")
    except Exception as e:
        print(f"[tv_history] connect failed: {e}")
        return None
    bars: list[list] = []
    try:
        _send(ws, {"m": "set_auth_token", "p": ["unauthorized_user_token"]})
        cs = _rand_id("cs_")
        _send(ws, {"m": "chart_create_session", "p": [cs, ""]})
        sds, cid = _rand_id("sds_"), _rand_id("s")
        _send(ws, {"m": "resolve_symbol", "p": [
            cs, sds, "=" + json.dumps({"symbol": f"{exchange}:{symbol}",
                                       "adjustment": "splits"})]})
        _send(ws, {"m": "create_series", "p": [cs, cid, "c1", sds, "1D",
                                               min(n_bars, 5000), ""]})
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            raw = ws.recv()
            for payload in _frames(raw):
                if payload.startswith("~h~"):
                    ws.send(_pack(payload))
                    continue
                msg = json.loads(payload)
                m = msg.get("m")
                if m == "timescale_update":
                    for item in msg["p"][1][cid]["s"]:
                        bars.append(item["v"])
                elif m == "series_completed":
                    if not bars:
                        return None
                    df = pd.DataFrame(bars, columns=["time", "Open", "High",
                                                     "Low", "Close", "Volume"])
                    df["date"] = pd.to_datetime(df["time"], unit="s")
                    df = (df.drop(columns="time").set_index("date")
                            .sort_index().astype(float))
                    return df
                elif m in ("symbol_error", "series_failed", "critical_error"):
                    print(f"[tv_history] {exchange}:{symbol} -> {m}: "
                          f"{str(msg.get('p'))[:120]}")
                    return None
        print(f"[tv_history] {exchange}:{symbol} timed out")
        return None
    except Exception as e:
        print(f"[tv_history] {exchange}:{symbol} error: {e}")
        return None
    finally:
        try:
            ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    d = tv_daily(sys.argv[1] if len(sys.argv) > 1 else "RELIANCE")
    if d is not None:
        print(f"rows={len(d)}  first={d.index[0].date()}  last={d.index[-1].date()}")
        print(d.tail(3))
