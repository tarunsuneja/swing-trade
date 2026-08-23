"""Sensitivity matrix for the Tier-II sympathy scan (robustness check)."""
import numpy as np
import pandas as pd

import test_tier2_sympathy as T
from strategy_validation import get_universe, load_data, stats


def build(data, smap, min_corr, min_lret):
    leaders = (smap.reset_index().sort_values("market_cap_basic", ascending=False)
               .groupby("sector").head(1)["symbol"].tolist())
    rets, vol_ok, liq_ok, uptrend = {}, {}, {}, {}
    for sym, df in data.items():
        r = df.Close.pct_change()
        rets[sym] = r
        vol_ok[sym] = df.Volume > 2 * df.Volume.rolling(20).mean()
        liq_ok[sym] = ((df.Close * df.Volume).rolling(50).mean() >= 5e7).reindex(r.index)
        c = df.Close
        uptrend[sym] = ((c > c.rolling(200).mean())
                        & (c.rolling(200).mean() > c.rolling(200).mean().shift(20))
                        ).reindex(r.index)
    R = pd.DataFrame(rets)
    rows = []
    sectors = smap["sector"].to_dict()
    for leader in leaders:
        sec = sectors.get(leader)
        if not sec or leader not in R.columns:
            continue
        mates = [s for s, x in sectors.items()
                 if x == sec and s != leader and s in R.columns]
        if not mates:
            continue
        l_ret = R[leader]
        l_evt = (l_ret >= min_lret) & vol_ok.get(leader, pd.Series(False, index=R.index))
        evt_dates = R.index[l_evt.fillna(False)]
        for mate in mates:
            corr = R[mate].rolling(120).corr(l_ret)
            up_s, lq_s = uptrend[mate], liq_ok[mate]
            for t in evt_dates:
                i = R.index.get_loc(t)
                if i < 130 or i + 1 >= len(R.index):
                    continue
                if not np.isfinite(corr.iloc[i]) or corr.iloc[i] < min_corr:
                    continue
                m_r = R[mate].iloc[i]
                if not np.isfinite(m_r) or m_r >= l_ret.iloc[i] / 2:
                    continue
                if t not in up_s.index or t not in lq_s.index:
                    continue
                if not bool(up_s.loc[t]) or not bool(lq_s.loc[t]):
                    continue
                rows.append({"symbol": mate, "date": R.index[i + 1]})
    return pd.DataFrame(rows).drop_duplicates()


def main():
    universe = get_universe()
    data, _ = load_data()
    smap = T.get_sector_map(universe)
    for mc, lr in [(0.55, 0.05), (0.60, 0.05), (0.45, 0.05),
                   (0.55, 0.04), (0.55, 0.06), (0.65, 0.06)]:
        sig = build(data, smap, mc, lr)
        tr = []
        for sym, grp in sig.groupby("symbol"):
            df = data.get(sym)
            idx = pd.DatetimeIndex([d for d in grp.date if d in df.index])
            tr += T.simulate_sympathy(df, idx)
        trd = pd.DataFrame(tr)
        if trd.empty:
            print(f"corr>={mc} lret>={lr}: no trades")
            continue
        s = stats(trd)
        print(f"corr>={mc} lret>={lr}: n={s['trades']:>4} win={s['win_pct']}% "
              f"avg={s['avg_ret_pct']}% PF={s['profit_factor']}")


if __name__ == "__main__":
    main()
