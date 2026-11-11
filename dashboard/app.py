"""
dashboard/app.py — Streamlit daily picks dashboard.

Tabs:
  🎯 Today's Picks   — BET signals ranked by edge
  🚫 Avoid List      — AVOID signals with negative edge
  📈 Performance     — Running P&L charts and win rates
  💰 Pick Log        — Full pick log with results
  ⚙️  Settings        — Config viewer (read-only)

Run:
    streamlit run dashboard/app.py
    streamlit run dashboard/app.py -- --date 2025-04-15
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def _fmt_et_time(iso: str | None) -> str:
    """ISO-8601 start time → 'h:mm AM/PM ET' (date only → 'M/D'); '' if absent."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:  # date-only (e.g. golf fallback) — no clock component
        return dt.strftime("%-m/%-d")
    et = dt.astimezone(ZoneInfo("America/New_York"))
    return et.strftime("%-I:%M %p ET")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import (
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    ACTION_MIN_PROB,
    ACTION_MIN_EDGE,
    ACTION_THRESHOLDS,
    RETIRED_MODELS,
    MODELS,
    MAX_KELLY_FRACTION,
    MIN_GAMES_BASELINE,
    MODEL_MIN_ODDS,
    PAPER_TRADING_START,
    PROB_ONLY_MODELS,
    duplicate_copy_exclusion_sql,
    record_exclusion_sql,
)

# Per-model action filter SQL fragment — inlined float constants, safe (no user input).
_ACTION_CLAUSES = []
_action_covered = set()
for _mid, _t in ACTION_THRESHOLDS.items():
    # Price floor (config.MODEL_MIN_ODDS): drop picks juicier than the model's
    # acceptable DK price. NULL dk_odds (prob-only fallback) always passes.
    _odds_clause = ""
    if _mid in MODEL_MIN_ODDS:
        _odds_clause = f" AND (dk_odds IS NULL OR dk_odds >= {MODEL_MIN_ODDS[_mid]})"
    if _mid in PROB_ONLY_MODELS:
        # Prob-only models: edge is not part of the BET decision (see config.PROB_ONLY_MODELS).
        _ACTION_CLAUSES.append(
            f"(model_id = '{_mid}' AND model_probability >= {_t['min_prob']}{_odds_clause})"
        )
    else:
        _ACTION_CLAUSES.append(
            f"(model_id = '{_mid}' AND model_probability >= {_t['min_prob']}"
            f" AND edge >= {_t['min_edge']}{_odds_clause})"
        )
    _action_covered.add(_mid)
# Fallback for any model not in ACTION_THRESHOLDS. A RETIRED model is not in
# ACTION_THRESHOLDS either, and without this exclusion it would be re-admitted
# here at the generic cut -- the same stale-row trap the app's RETIRED_MODELS
# guard exists for.
_action_covered |= set(RETIRED_MODELS)
_ACTION_CLAUSES.append(
    f"(model_id NOT IN ({','.join(repr(m) for m in sorted(_action_covered))})"
    f" AND model_probability >= {ACTION_MIN_PROB}"
    f" AND edge >= {ACTION_MIN_EDGE})"
)
_ACTION_FILTER = "(" + " OR ".join(_ACTION_CLAUSES) + ")"
# What a record query excludes: RECORD_EXCLUSIONS and the second copy of one
# bet stored under two game ids. Never a threshold (CLAUDE.md §1c).
_RECORD_EXCLUSIONS = record_exclusion_sql("picks") + duplicate_copy_exclusion_sql("picks")
_LOG_EXCLUSIONS = record_exclusion_sql("p") + duplicate_copy_exclusion_sql("p")
from data.db import get_connection
from tracking.discord_notifier import (
    MAX_RISK_UNITS, fmt_stake, fmt_units, stake_for, units_for,
)
from tracking.published_units import unit_profit

# ── Units (CLAUDE.md §4) ──────────────────────────────────────────────────────
# Results and stakes are shown in units, never dollars, on ONE basis: the
# published stake (CLAUDE.md §2), stake_for: 1u to win at
# COALESCE(decision_odds, dk_odds), risk capped at 3u, a pick with no price at
# the bare 1u. It is what Discord #results and the app's Record tab book
# (published_pick_unit_profit / _risked), so the totals below read the same
# v_public_track_record views and a model shows the same units everywhere.
# profit_flat (per $100 staked, 1u RISKED) is not shown: it is another basis,
# and it invents -110 on a pick with no price. The paper Kelly bankroll
# (recommended_bet, profit_kelly, bankroll_at_pick) is dollars on a roll no
# published stake uses; not shown.
#
# Record queries filter on what the pick WAS (signal_type = 'BET', a result,
# the window) and never re-cut with today's action filter (CLAUDE.md §1c).
# Only Today's Picks and Avoid Signals, the live board, apply _ACTION_FILTER.

def _price_or_none(decision_odds, dk_odds):
    """COALESCE(decision_odds, dk_odds). pandas hands a missing one over as NaN."""
    for price in (decision_odds, dk_odds):
        if price is not None and pd.notna(price):
            return float(price)
    return None


def _units_cell(result, price, stake_units=None) -> str:
    """The published stake's result: '+1.00u', '-2.00u' (a -200 loss), '0.00u'
    on a push; '–' until the pick grades. No price is the bare stake.
    `stake_units` is the pick's own stake (picks.stake_units); None is 1u."""
    if not isinstance(result, str) or result not in ("WIN", "LOSS", "PUSH"):
        return "–"
    u = unit_profit(None if price is None or pd.isna(price) else float(price), result,
                    _stake_or_none(stake_units))
    return "0.00u" if round(u, 2) == 0 else f"{u:+.2f}u"


def _stake_or_none(stake_units):
    """picks.stake_units as a float, or None (1u) when it is missing or NaN."""
    if stake_units is None or pd.isna(stake_units):
        return None
    return float(stake_units)


def _stake_cell(kelly_fraction, decision_odds, dk_odds, stake_units=None) -> str:
    """The published stake: '1.1u to win 1u', or '1u' with no price."""
    return fmt_stake(stake_for(kelly_fraction, _price_or_none(decision_odds, dk_odds),
                               _stake_or_none(stake_units)))


def _units_at_risk(rows) -> str:
    """Units laid across (kelly_fraction, decision_odds, dk_odds[, stake_units]) rows."""
    return fmt_units(sum(units_for(r[0], _price_or_none(r[1], r[2]),
                                   _stake_or_none(r[3] if len(r) > 3 else None))
                         for r in map(tuple, rows)))


# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Betting Model Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom Styles ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .metric-card {
        background: #1e2130;
        border-radius: 8px;
        padding: 16px;
        margin: 4px;
    }
    .bet-signal  { color: #00d4aa; font-weight: bold; }
    .avoid-signal { color: #ff6b6b; font-weight: bold; }
    .high-tier   { background: rgba(0,212,170,0.15); border-left: 3px solid #00d4aa; }
    .med-tier    { background: rgba(255,193,7,0.1);  border-left: 3px solid #ffc107; }
    .low-tier    { background: rgba(108,117,125,0.1); border-left: 3px solid #6c757d; }
    .stDataFrame { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ── DB Connection ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    # Returns a raw psycopg2 connection for use with pd.read_sql_query.
    # cache_resource keeps it alive for the Streamlit session.
    from config import DATABASE_URL
    pg = psycopg2.connect(DATABASE_URL)
    pg.autocommit = True  # read-only dashboard — no transactions needed
    return pg


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Execute a SQL query and return a DataFrame."""
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=params or None)
    except Exception as exc:
        st.error(f"Query error: {exc}\n\n```sql\n{sql}\n```")
        return pd.DataFrame()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🎯 Betting Model")
    st.caption("Signal Tracking")
    st.divider()

    selected_date = st.date_input(
        "Viewing Date",
        value=date.today(),
        min_value=date(2019, 1, 1),
        max_value=date.today() + timedelta(days=1),
    )
    selected_date_str = selected_date.isoformat()

    sport_filter = st.multiselect(
        "Sport",
        options=["MLB", "NHL"],
        default=["MLB", "NHL"],
    )

    tier_filter = st.multiselect(
        "Confidence Tier",
        options=["HIGH", "MED", "LOW"],
        default=["HIGH", "MED", "LOW"],
    )

    st.divider()

    # 7-day summary from the published daily record: the same units the
    # app's Record tab and Discord show for these days.
    week_ago = max((date.today() - timedelta(days=7)).isoformat(), PAPER_TRADING_START)
    week_stats = query("""
        SELECT SUM(wins) AS wins, SUM(losses) AS losses,
               SUM(units) AS units, SUM(risked) AS risked
        FROM v_public_track_record_daily
        WHERE game_date >= %s
    """, (week_ago,))

    if not week_stats.empty and week_stats["wins"].iloc[0] is not None:
        w = int(week_stats["wins"].iloc[0] or 0)
        l = int(week_stats["losses"].iloc[0] or 0)
        u = week_stats["units"].iloc[0]
        units = float(u) if u is not None and pd.notna(u) else 0.0
        st.caption(f"Last 7 days: {w}W/{l}L | {units:+.2f}u (as published)")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_picks, tab_avoid, tab_perf, tab_log, tab_settings = st.tabs([
    "🎯 Today's Picks",
    "🚫 Avoid List",
    "📈 Performance",
    "💰 Pick Log",
    "⚙️ Settings",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: TODAY'S PICKS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_picks:
    st.header(f"🎯 BET Signals — {selected_date_str}")

    sport_placeholder = ",".join(f"'{s}'" for s in sport_filter)
    tier_placeholder  = ",".join(f"'{t}'" for t in tier_filter)

    picks_df = query(f"""
        SELECT p.pick_label, p.model_id, p.sport, p.game_time,
               p.model_probability, p.dk_implied_prob,
               p.edge, p.dk_odds, p.decision_odds, p.kelly_fraction,
               p.confidence_tier, p.injury_flag, p.injury_detail,
               p.public_bet_pct, p.public_money_pct,
               p.result, g.home_team, g.away_team, g.home_score, g.away_score,
               p.pick_side, p.stake_units
        FROM picks p
        LEFT JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.signal_type = 'BET'
          AND {_ACTION_FILTER}
          AND p.sport IN ({sport_placeholder})
          AND p.confidence_tier IN ({tier_placeholder})
        ORDER BY p.edge DESC
    """, (selected_date_str,))

    if picks_df.empty:
        st.info(f"No BET signals for {selected_date_str}. "
                f"Check if the scorer has run for this date.")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total BETs", len(picks_df))
        with col2:
            avg_edge = picks_df["edge"].mean()
            st.metric("Avg Edge", f"{avg_edge:.1%}")
        with col3:
            st.metric("Units at Risk", _units_at_risk(zip(
                picks_df["kelly_fraction"], picks_df["decision_odds"],
                picks_df["dk_odds"], picks_df["stake_units"])))
        with col4:
            high_tier = len(picks_df[picks_df["confidence_tier"] == "HIGH"])
            st.metric("HIGH Confidence", high_tier)

        st.divider()

        # Per-pick cards
        for _, row in picks_df.iterrows():
            tier_class = row["confidence_tier"].lower() + "-tier"
            inj_badge  = f"⚠️ {row['injury_flag']}" if row["injury_flag"] else ""
            result_badge = ""
            if row["result"]:
                r = row["result"]
                result_badge = ("✅ WIN" if r == "WIN" else
                                "❌ LOSS" if r == "LOSS" else
                                "↩️ PUSH" if r == "PUSH" else r)

            with st.container():
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
                with c1:
                    st.markdown(f"**{row['pick_label']}**  "
                                f"`{row['model_id']}` "
                                f"{inj_badge}")
                    start_str = _fmt_et_time(row.get("game_time"))
                    matchup = f"{row['home_team']} vs {row['away_team']}"
                    st.caption(
                        f"{row['sport']} | {matchup}"
                        + (f" | 🕒 {start_str}" if start_str else "")
                    )
                with c2:
                    st.metric("Model %", f"{row['model_probability']:.1%}")
                with c3:
                    st.metric("DK %", f"{row['dk_implied_prob']:.1%}")
                with c4:
                    st.metric("Edge", f"{row['edge']:.1%}")
                with c5:
                    st.metric("Stake", _stake_cell(row["kelly_fraction"],
                                                   row["decision_odds"],
                                                   row["dk_odds"],
                                                   row.get("stake_units")))

                # Public betting coverage (Action Network) — fade-the-public context
                pb = row.get("public_bet_pct")
                pm = row.get("public_money_pct")
                if pb is not None or pm is not None:
                    bet_str   = f"{pb:.0f}%" if pb is not None else "—"
                    money_str = f"{pm:.0f}%" if pm is not None else "—"
                    st.caption(f"👥 Public on this side — bets: {bet_str} | money: {money_str}")

                if row["injury_detail"]:
                    st.caption(f"🏥 {row['injury_detail']}")
                if result_badge:
                    st.markdown(result_badge)

                st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: AVOID LIST
# ═══════════════════════════════════════════════════════════════════════════════

with tab_avoid:
    st.header(f"🚫 AVOID Signals — {selected_date_str}")
    st.caption("These games have significant negative edge — the market has it right or our model sees value the other way.")

    avoids_df = query(f"""
        SELECT p.pick_label, p.model_id, p.sport,
               p.model_probability, p.dk_implied_prob,
               p.edge, p.dk_odds, p.confidence_tier,
               p.injury_flag, p.injury_detail, p.result,
               g.home_team, g.away_team
        FROM picks p
        LEFT JOIN games g ON p.game_id = g.game_id
        WHERE p.game_date = %s
          AND p.signal_type = 'AVOID'
          AND p.sport IN ({sport_placeholder})
        ORDER BY p.edge ASC
    """, (selected_date_str,))

    if avoids_df.empty:
        st.info(f"No AVOID signals for {selected_date_str}.")
    else:
        st.metric("Total AVOIDs", len(avoids_df))
        st.dataframe(
            avoids_df[["pick_label", "sport", "model_id",
                        "model_probability", "dk_implied_prob",
                        "edge", "confidence_tier", "injury_flag"]].rename(columns={
                "pick_label":       "Pick",
                "model_id":         "Model",
                "model_probability": "Model %",
                "dk_implied_prob":  "DK %",
                "edge":             "Edge",
                "confidence_tier":  "Tier",
                "injury_flag":      "Injury",
            }),
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════

with tab_perf:
    st.header("📈 Performance Analytics")

    lookback = st.selectbox("Lookback Window", [7, 14, 30, 60, 90, 365],
                             index=2, format_func=lambda x: f"{x} days")
    cutoff = max((date.today() - timedelta(days=lookback)).isoformat(), PAPER_TRADING_START)

    # ── Running units chart ────────────────────────────────────────────────────
    # The published daily record, summed day by day: the app's equity curve.
    units_hist = query("""
        SELECT game_date, SUM(units) AS units, SUM(risked) AS risked
        FROM v_public_track_record_daily
        WHERE game_date >= %s
        GROUP BY game_date
        ORDER BY game_date
    """, (cutoff,))

    if not units_hist.empty:
        units_hist["units"] = units_hist["units"].astype(float).cumsum()
        fig = px.line(units_hist, x="game_date", y="units",
                      title="Running Units (as published: 1u to win per pick)",
                      labels={"game_date": "Date", "units": "Units"},
                      line_shape="spline")
        fig.add_hline(y=0, line_dash="dash", line_color="gray",
                      annotation_text="Break-even")
        fig.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                           font_color="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Win rate and return by model ──────────────────────────────────────────
    # The published per-model record since the record start, the same rows
    # and units as the app's Models list and Record tab. Not windowed: the
    # lookback above is for the charts.
    model_perf = query("""
        SELECT model_id, sport, picks, wins, losses, pushes,
               ROUND(wins::numeric / NULLIF(wins + losses, 0), 3) AS win_rate,
               ROUND(units, 2) AS units,
               ROUND(risked, 2) AS risked,
               ROUND(units / NULLIF(risked, 0), 3) AS roi
        FROM v_public_track_record
        ORDER BY roi DESC NULLS LAST
    """)

    if not model_perf.empty:
        col_l, col_r = st.columns(2)
        with col_l:
            fig2 = px.bar(model_perf, x="model_id", y="win_rate",
                          color="sport", title="Win Rate by Model",
                          labels={"model_id": "", "win_rate": "Win Rate"},
                          barmode="group")
            fig2.add_hline(y=0.5, line_dash="dash", line_color="gray")
            fig2.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                               font_color="white")
            st.plotly_chart(fig2, use_container_width=True)

        with col_r:
            fig3 = px.bar(model_perf, x="model_id", y="roi",
                          color="sport", title="Return on Bets by Model (as published)",
                          labels={"model_id": "", "roi": "Units won / units risked"},
                          barmode="group")
            fig3.add_hline(y=0, line_dash="dash", line_color="gray")
            fig3.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                               font_color="white")
            st.plotly_chart(fig3, use_container_width=True)

        st.dataframe(model_perf, use_container_width=True)

    # ── Calibration chart ─────────────────────────────────────────────────────
    cal_df = query(f"""
        SELECT model_probability, result
        FROM picks
        WHERE game_date >= %s
          AND result IN ('WIN','LOSS')
          AND signal_type = 'BET'{_RECORD_EXCLUSIONS}
    """, (cutoff,))

    if len(cal_df) >= 20:
        cal_df["won"] = (cal_df["result"] == "WIN").astype(int)
        cal_df["bin"] = pd.cut(cal_df["model_probability"],
                                bins=[0, .4, .45, .5, .55, .6, .65, .7, 1],
                                labels=[".35-.40",".40-.45",".45-.50",
                                        ".50-.55",".55-.60",".60-.65",
                                        ".65-.70",".70+"])
        cal_agg = cal_df.groupby("bin").agg(
            mean_pred=("model_probability", "mean"),
            mean_actual=("won", "mean"),
            n=("won", "count"),
        ).reset_index()

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=cal_agg["mean_pred"], y=cal_agg["mean_actual"],
                                   mode="markers+lines", name="Calibration",
                                   marker=dict(size=cal_agg["n"]/2, sizemin=4)))
        fig4.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                   name="Perfect Cal.", line=dict(dash="dash", color="gray")))
        fig4.update_layout(title="Model Calibration Plot",
                            xaxis_title="Predicted Probability",
                            yaxis_title="Actual Win Rate",
                            plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                            font_color="white")
        st.plotly_chart(fig4, use_container_width=True)

    # ── Edge distribution ─────────────────────────────────────────────────────
    edge_df = query(f"""
        SELECT edge, result, sport
        FROM picks
        WHERE game_date >= %s AND signal_type = 'BET' AND result IS NOT NULL{_RECORD_EXCLUSIONS}
    """, (cutoff,))

    if not edge_df.empty:
        fig5 = px.histogram(edge_df, x="edge", color="result",
                             title="Edge Distribution (BET signals)",
                             labels={"edge": "Edge", "result": "Result"},
                             nbins=30, barmode="overlay", opacity=0.7,
                             color_discrete_map={"WIN": "#00d4aa", "LOSS": "#ff6b6b"})
        fig5.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                            font_color="white")
        st.plotly_chart(fig5, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: PICK LOG
# ═══════════════════════════════════════════════════════════════════════════════

with tab_log:
    st.header("💰 Pick Log")

    log_lookback = st.slider("Days to show", 1, 90, 14)
    log_cutoff   = max((date.today() - timedelta(days=log_lookback)).isoformat(), PAPER_TRADING_START)

    log_df = query(f"""
        SELECT p.game_date, p.sport, p.pick_label, p.model_id,
               p.signal_type, p.confidence_tier,
               p.model_probability, p.dk_implied_prob,
               p.edge, p.dk_odds, p.decision_odds, p.kelly_fraction,
               p.result, p.profit_flat,
               p.injury_flag, p.stake_units
        FROM picks p
        WHERE p.game_date >= %s
          AND p.signal_type = 'BET'{_LOG_EXCLUSIONS}
        ORDER BY p.game_date DESC, p.edge DESC
    """, (log_cutoff,))

    if log_df.empty:
        st.info("No picks found in this time range.")
    else:
        # Color-code results
        def _style_result(val):
            if val == "WIN":  return "color: #00d4aa; font-weight: bold"
            if val == "LOSS": return "color: #ff6b6b; font-weight: bold"
            if val == "PUSH": return "color: #ffc107"
            return ""

        def _style_signal(val):
            if val == "BET":   return "color: #00d4aa"
            if val == "AVOID": return "color: #ff6b6b"
            return ""

        # Format percentages
        log_df["model_probability"] = log_df["model_probability"].map(lambda x: f"{x:.1%}" if x else "–")
        log_df["dk_implied_prob"]   = log_df["dk_implied_prob"].map(lambda x: f"{x:.1%}" if x else "–")
        log_df["edge"]              = log_df["edge"].map(lambda x: f"{x:+.1%}" if x else "–")
        # Stake and result in units (§4), beside the result.
        stake = [_stake_cell(k, d, o, u) for k, d, o, u in zip(
            log_df["kelly_fraction"], log_df["decision_odds"], log_df["dk_odds"],
            log_df["stake_units"])]
        units = [_units_cell(r, _price_or_none(d, o), u) for r, d, o, u in zip(
            log_df["result"], log_df["decision_odds"], log_df["dk_odds"], log_df["stake_units"])]
        log_df = log_df.drop(columns=["kelly_fraction", "profit_flat", "stake_units"])
        at = log_df.columns.get_loc("result")
        log_df.insert(at, "stake", stake)
        log_df.insert(at + 2, "units", units)

        # Styler.map (pandas >= 2.1; requirements-dashboard pins >= 2.2).
        # applymap is gone in pandas 3 and took the whole tab down with it.
        styled = log_df.style.map(_style_result, subset=["result"]) \
                             .map(_style_signal, subset=["signal_type"])

        st.dataframe(styled, use_container_width=True, height=600)

        # Download button
        st.download_button(
            label="📥 Download CSV",
            data=log_df.to_csv(index=False),
            file_name=f"picks_{log_cutoff}_to_{date.today().isoformat()}.csv",
            mime="text/csv",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

with tab_settings:
    st.header("⚙️ Configuration")
    st.caption("Read-only view. Edit values in your .env file, then restart the pipeline.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Model Thresholds")
        st.json({
            "BET_EDGE_THRESHOLD":   f"{BET_EDGE_THRESHOLD:.1%}",
            "AVOID_EDGE_THRESHOLD": f"{AVOID_EDGE_THRESHOLD:.1%}",
            "MAX_KELLY_FRACTION":   f"{MAX_KELLY_FRACTION:.1%}",
            "MIN_GAMES_BASELINE":   MIN_GAMES_BASELINE,
            "STAKE":                f"1u to win, risk capped at {fmt_units(MAX_RISK_UNITS)}",
        })

        st.subheader("Active Models")
        model_registry = query("""
            SELECT model_id, version, trained_on, holdout_accuracy,
                   holdout_roi, holdout_picks, is_active
            FROM model_registry
            ORDER BY model_id, created_at DESC
        """)
        if not model_registry.empty:
            st.dataframe(model_registry, use_container_width=True)
        else:
            st.info("No models trained yet. Run: `python -m models.trainer --all`")

    with col2:
        st.subheader("Pipeline Log (last 7 days)")
        pipeline_log = query("""
            SELECT run_date, step, status, records_in, records_out,
                   ROUND(duration_s, 1) as duration_s, error_msg
            FROM pipeline_log
            WHERE run_date >= %s
            ORDER BY created_at DESC
            LIMIT 50
        """, ((date.today() - timedelta(days=7)).isoformat(),))

        if not pipeline_log.empty:
            st.dataframe(pipeline_log, use_container_width=True)
        else:
            st.info("No pipeline runs logged yet.")

        st.subheader("Database Stats")
        tables = ["games", "odds", "injuries", "picks",
                  "mlb_team_stats", "nhl_team_stats",
                  "mlb_pitcher_stats", "nhl_goalie_stats"]
        stats = {}
        for t in tables:
            row = query(f"SELECT COUNT(*) as n FROM {t}")
            stats[t] = int(row["n"].iloc[0]) if not row.empty else 0
        st.json(stats)
