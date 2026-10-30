"""Contract-roll selection rule (synthetic cases + real-data invariants)."""
import pandas as pd
import pytest

from ict_lab.engine.rolls import RollRule, select_active_contracts


def rule(**kw) -> RollRule:
    base = dict(confirmation_days=1, forward_only=True, tie_break="incumbent", reference_minute=1019, reference_price_field="close")
    base.update(kw)
    return RollRule(**base)


def dv_frame(rows, cols):
    idx = pd.to_datetime([f"2024-01-{d:02d}" for d in range(1, len(rows) + 1)])
    return pd.DataFrame(rows, index=idx, columns=cols).rename_axis("trading_date")


def test_crossover_takes_effect_next_day(spec):
    dv = dv_frame([[100, 10], [100, 50], [90, 120], [20, 200], [1, 300]], ["MNQH4", "MNQM4"])
    sel, ev = select_active_contracts(dv, rule(), spec)
    assert sel["active_symbol"].tolist() == ["MNQH4", "MNQH4", "MNQH4", "MNQM4", "MNQM4"]
    assert len(ev) == 1 and str(ev[0]["crossover_trading_date"].date()) == "2024-01-03" and str(ev[0]["effective_trading_date"].date()) == "2024-01-04"


def test_tie_keeps_incumbent(spec):
    dv = dv_frame([[100, 10], [100, 100], [100, 100], [10, 101], [10, 101]], ["MNQH4", "MNQM4"])
    sel, ev = select_active_contracts(dv, rule(), spec)
    assert sel["active_symbol"].tolist() == ["MNQH4", "MNQH4", "MNQH4", "MNQH4", "MNQM4"]


def test_never_rolls_backward(spec):
    dv = dv_frame([[10, 100], [500, 100], [500, 100]], ["MNQH4", "MNQM4"])   # H4 out-trades M4 after init on M4
    sel, ev = select_active_contracts(dv, rule(), spec)
    assert sel["active_symbol"].tolist() == ["MNQM4"] * 3 and ev == []


def test_multiple_candidates_prefers_highest_volume(spec):
    dv = dv_frame([[100, 1, 1], [10, 50, 80], [10, 50, 80]], ["MNQH4", "MNQM4", "MNQU4"])
    sel, ev = select_active_contracts(dv, rule(), spec)
    assert sel["active_symbol"].tolist() == ["MNQH4", "MNQH4", "MNQU4"] and ev[0]["n_candidates"] == 2


def test_confirmation_days_two(spec):
    dv = dv_frame([[100, 10], [10, 100], [100, 10], [10, 100], [10, 100], [10, 100]], ["MNQH4", "MNQM4"])
    sel, ev = select_active_contracts(dv, rule(confirmation_days=2), spec)
    # single-day spikes on day 2 do not roll; days 4+5 both exceed -> effective day 6
    assert sel["active_symbol"].tolist() == ["MNQH4"] * 5 + ["MNQM4"]


def test_zero_volume_active_contract_is_an_error(spec):
    dv = dv_frame([[100, 10], [0, 5]], ["MNQH4", "MNQM4"])
    with pytest.raises(RuntimeError):
        select_active_contracts(dv, rule(), spec)


# ------------------------------------------------------------------ real data
EXPECTED_TRANSITIONS = [("MNQZ2", "MNQH3"), ("MNQH3", "MNQM3"), ("MNQM3", "MNQU3"), ("MNQU3", "MNQZ3"), ("MNQZ3", "MNQH4"),
                        ("MNQH4", "MNQM4"), ("MNQM4", "MNQU4"), ("MNQU4", "MNQZ4"), ("MNQZ4", "MNQH5"), ("MNQH5", "MNQM5"),
                        ("MNQM5", "MNQU5"), ("MNQU5", "MNQZ5"), ("MNQZ5", "MNQH6"), ("MNQH6", "MNQM6"), ("MNQM6", "MNQU6"),
                        ("MNQU6", "MNQZ6")]


def test_real_roll_log_matches_audit_transitions(rolls_csv, session_table):
    assert list(zip(rolls_csv["old_symbol"], rolls_csv["new_symbol"])) == EXPECTED_TRANSITIONS
    dates = session_table["trading_date"].sort_values().reset_index(drop=True)
    nxt = dict(zip(dates[:-1], dates[1:]))
    for _, r in rolls_csv.iterrows():
        assert nxt[r["crossover_trading_date"]] == r["effective_trading_date"]      # effective = next session
        assert r["new_volume_crossover_date"] > r["old_volume_crossover_date"]      # strict crossover
        assert r["old_volume_effective_date"] >= 0
    assert (rolls_csv["reference_fallback_minutes"] == 0).all()
    assert (rolls_csv["ref_minute_of_day_ny"] == 16 * 60 + 59).all()


def test_real_active_contract_has_no_lookahead(clean_dir, rolls_csv):
    sel = pd.read_csv(clean_dir / "MNQ_active_contract_by_date.csv", parse_dates=["trading_date", "decision_basis_date"])
    assert sel["decision_basis_date"].iloc[0] != sel["decision_basis_date"].iloc[0]  # NaT for the initial date
    later = sel.iloc[1:]
    assert (later["decision_basis_date"] < later["trading_date"]).all()
