"""Volume-crossover contract selection and roll log.

Rule (all terms defined, see configs/layer1_data.toml [roll]):

  eligibility   outright quarterly contracts only (instrument.outright_symbol_regex)
  daily volume  V[D, c] = sum of 1-minute volume of contract c over CME trading date D
  incumbent     A(D) = contract selected for trading date D
  challenger    any contract c with expiry(c) > expiry(A) [forward_only]
  crossover     on trading date D, V[D, c] > V[D, A(D)] for `confirmation_days` consecutive
                trading dates ending at D (strict inequality; a tie keeps the incumbent)
  selection     if several challengers cross on the same date the one with the highest V[D, c]
                wins; an exact tie among challengers goes to the earliest expiry
  effective     the new contract is used from the NEXT trading date D+1 onward, so the decision
                for a session only uses volume from sessions that already closed (no look-ahead)
  roll ts       first bar of the new contract in the effective session (nominally 18:00 ET of
                the calendar day before D+1)
  offset        price_new - price_old at the reference minute on crossover date D (16:59 ET close
                by default), stepping back one minute at a time within session D if either
                contract has no bar at that minute (flagged)
  initialization  the very first trading date in the data uses its own session volume to pick
                the starting contract (the only place same-day volume is used; flagged)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .instrument import InstrumentSpec, contract_sort_key, expiry_order
from .sessions import SessionSpec


@dataclass(frozen=True)
class RollRule:
    confirmation_days: int
    forward_only: bool
    tie_break: str
    reference_minute: int          # minutes after midnight NY
    reference_price_field: str

    @classmethod
    def from_config(cls, cfg) -> "RollRule":
        r = cfg["roll"]
        if r["method"] != "volume_crossover":
            raise ValueError(f"unsupported roll method {r['method']}")
        h, m = r["reference_minute"].split(":")
        return cls(confirmation_days=int(r["confirmation_days"]), forward_only=bool(r["forward_only"]),
                   tie_break=r["tie_break"], reference_minute=int(h) * 60 + int(m),
                   reference_price_field=r["reference_price_field"])


def daily_volume(bars: pd.DataFrame) -> pd.DataFrame:
    """Pivot: index = trading_date (sorted), columns = symbol, values = summed volume (0 if absent)."""
    dv = bars.groupby(["trading_date", "symbol"], observed=True)["volume"].sum().unstack("symbol").fillna(0)
    dv = dv.sort_index()
    dv = dv[expiry_order(list(dv.columns))]
    return dv.astype("int64")


def select_active_contracts(dv: pd.DataFrame, rule: RollRule, spec: InstrumentSpec) -> tuple[pd.DataFrame, list[dict]]:
    """Returns (selection, events).
    selection: DataFrame indexed by trading_date with columns active_symbol, decision_basis_date.
    events: list of dicts describing each roll (crossover_date, effective_date, old, new, volumes)."""
    dates = list(dv.index)
    syms = list(dv.columns)
    order = {s: contract_sort_key(s, spec.root) for s in syms}
    active: list[str] = []
    basis: list[pd.Timestamp | None] = []
    events: list[dict] = []
    first = dv.iloc[0]
    if first.sum() == 0:
        raise RuntimeError("no volume on the first trading date; cannot initialise contract selection")
    cur = first.idxmax()  # initialization: same-day volume, flagged in the log
    active.append(cur); basis.append(None)
    for i in range(1, len(dates)):
        # decision for dates[i] uses sessions dates[i-k] .. dates[i-1]
        window = dv.iloc[max(0, i - rule.confirmation_days): i]
        if len(window) < rule.confirmation_days:
            active.append(cur); basis.append(dates[i - 1]); continue
        inc_vol = window[cur]
        candidates = []
        for s in syms:
            if s == cur:
                continue
            if rule.forward_only and order[s] <= order[cur]:
                continue
            if bool((window[s] > inc_vol).all()):
                candidates.append(s)
        if candidates:
            last = dv.iloc[i - 1]
            # highest volume on the crossover date, tie -> earliest expiry
            candidates.sort(key=lambda s: (-int(last[s]), order[s]))
            new = candidates[0]
            events.append({
                "old_symbol": cur, "new_symbol": new,
                "crossover_trading_date": dates[i - 1], "effective_trading_date": dates[i],
                "old_volume_crossover_date": int(last[cur]), "new_volume_crossover_date": int(last[new]),
                "old_volume_effective_date": int(dv.iloc[i][cur]), "new_volume_effective_date": int(dv.iloc[i][new]),
                "n_candidates": len(candidates),
            })
            cur = new
        active.append(cur); basis.append(dates[i - 1])
    sel = pd.DataFrame({"trading_date": dates, "active_symbol": active, "decision_basis_date": basis}).set_index("trading_date")
    # sanity: the active contract must have traded on every date it is selected for
    missing = [(d, s) for d, s in zip(dates, active) if dv.loc[d, s] == 0]
    if missing:
        raise RuntimeError(f"active contract has zero volume on its selected date(s): {missing[:5]}")
    return sel, events


def reference_prices(bars: pd.DataFrame, sessions: SessionSpec, rule: RollRule, old: str, new: str,
                     crossover_date: pd.Timestamp) -> dict:
    """Synchronised prices for `old` and `new` at the reference minute of the crossover session,
    stepping back minute by minute within that session until both contracts have a bar."""
    day = bars[(bars["trading_date"] == crossover_date) & (bars["symbol"].isin([old, new]))]
    po = day[day.symbol == old].set_index("minute_of_day_ny")
    pn = day[day.symbol == new].set_index("minute_of_day_ny")
    common = po.index.intersection(pn.index)
    if len(common) == 0:
        raise RuntimeError(f"no synchronised minute for {old}/{new} on {crossover_date.date()}")
    # candidate minutes at or before the reference minute, in session order (18:00 .. 16:59)
    def session_rank(m: int) -> int:  # minutes since 18:00 open
        return (m - sessions.open_minute) % 1440
    ref_rank = session_rank(rule.reference_minute)
    ranked = sorted(((session_rank(m), m) for m in common if session_rank(m) <= ref_rank), reverse=True)
    if not ranked:
        raise RuntimeError(f"no synchronised minute at/before reference on {crossover_date.date()} for {old}/{new}")
    rank, minute = ranked[0]
    fallback = ref_rank - rank
    f = rule.reference_price_field
    return {
        "ref_ts_utc": po.loc[minute, "ts_utc"], "ref_minute_of_day_ny": int(minute),
        "ref_price_old": float(po.loc[minute, f]), "ref_price_new": float(pn.loc[minute, f]),
        "reference_fallback_minutes": int(fallback),
    }


def build_roll_log(bars: pd.DataFrame, sel: pd.DataFrame, events: list[dict], sessions: SessionSpec,
                   rule: RollRule, spec: InstrumentSpec) -> pd.DataFrame:
    rows = []
    for k, ev in enumerate(events, start=1):
        rp = reference_prices(bars, sessions, rule, ev["old_symbol"], ev["new_symbol"], ev["crossover_trading_date"])
        eff = ev["effective_trading_date"]
        new_bars = bars[(bars.trading_date == eff) & (bars.symbol == ev["new_symbol"])]
        roll_ts = new_bars["ts_utc"].min()
        offset = rp["ref_price_new"] - rp["ref_price_old"]
        rows.append({
            "roll_id": k, **ev,
            "nominal_session_open_utc": sessions.session_open_utc(eff),
            "roll_ts_utc": roll_ts, **rp,
            "offset_points": offset, "offset_ticks": offset / spec.tick_size,
            "offset_is_tick_multiple": spec.is_tick_multiple(offset),
        })
    log = pd.DataFrame(rows)
    if len(log):
        # anchor = latest contract: adjustment applied to bars BEFORE roll k is the sum of offsets k..n
        log["cumulative_adjustment_before_roll"] = log["offset_points"][::-1].cumsum()[::-1]
        log["cumulative_adjustment_after_roll"] = log["cumulative_adjustment_before_roll"] - log["offset_points"]
        log["roll_ts_ny"] = pd.DatetimeIndex(log["roll_ts_utc"]).tz_convert(sessions.timezone)
        log["ref_ts_ny"] = pd.DatetimeIndex(log["ref_ts_utc"]).tz_convert(sessions.timezone)
        vol_ratio = log["new_volume_crossover_date"] / log["old_volume_crossover_date"].replace(0, np.nan)
        log["crossover_volume_ratio"] = vol_ratio
        log["near_tie_crossover"] = vol_ratio < 1.05
    return log
