"""
dashboard/app.py — Streamlit daily picks dashboard.

Tabs:
  🎯 Today's Picks   — BET signals ranked by edge
  🚫 Avoid List      — AVOID signals with negative edge
  📈 Performance     — Running P&L charts and win rates
  💰 Paper Trading   — Full pick log with results
  ⚙️  Settings        — Config viewer (read-only)

Run:
    streamlit run dashboard/app.py
    streamlit run dashboard/app.py -- --date 2025-04-15
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import (
    BANKROLL,
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    ACTION_MIN_PROB,
    ACTION_MIN_EDGE,
    ML_ACTION_MIN_PROB,
    ML_ACTION_MIN_EDGE,
    MODELS,
    MAX_KELLY_FRACTION,
    MIN_GAMES_BASELINE,
)

# Per-model action filter SQL fragment — inlined float constants, safe (no user input).
_ML_MODELS = "'mlb_moneyline', 'mlb_runline'"
_ACTION_FILTER = (
    f"((model_id IN ({_ML_MODELS}) AND model_probability >= {ML_ACTION_MIN_PROB}"
    f" AND edge >= {ML_ACTION_MIN_EDGE})"
    f" OR (model_id NOT IN ({_ML_MODELS}) AND model_probability >= {ACTION_MIN_PROB}"
    f" AND edge >= {ACTION_MIN_EDGE}))"
)
from data.db import get_connection

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
    st.caption("Paper Trading Mode")
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

    # Live bankroll
    bankroll_row = query("""
        SELECT bankroll_at_pick + COALESCE(profit_kelly, 0) as current
        FROM picks
        WHERE result IS NOT NULL
        ORDER BY settled_at DESC
        LIMIT 1
    """)
    current_bankroll = (bankroll_row["current"].iloc[0]
                         if not bankroll_row.empty else BANKROLL)

    st.metric("💰 Bankroll", f"${current_bankroll:,.2f}",
               delta=f"${current_bankroll - BANKROLL:+,.2f}")

    # 7-day summary (action-filter picks only: prob >= 65%, edge >= 14%)
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    week_stats = query("""
        SELECT
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(profit_flat) as pnl
        FROM picks
        WHERE game_date >= %s AND result IS NOT NULL AND signal_type='BET'
          AND {_ACTION_FILTER}
    """, (week_ago,))

    if not week_stats.empty and week_stats["wins"].iloc[0] is not None:
        w = int(week_stats["wins"].iloc[0] or 0)
        l = int(week_stats["losses"].iloc[0] or 0)
        pnl = float(week_stats["pnl"].iloc[0] or 0)
        st.caption(f"Last 7 days: {w}W/{l}L | ${pnl:+,.2f}")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_picks, tab_avoid, tab_perf, tab_log, tab_settings = st.tabs([
    "🎯 Today's Picks",
    "🚫 Avoid List",
    "📈 Performance",
    "💰 Paper Trading",
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
        SELECT p.pick_label, p.model_id, p.sport,
               p.model_probability, p.dk_implied_prob,
               p.edge, p.dk_odds, p.kelly_fraction, p.recommended_bet,
               p.confidence_tier, p.injury_flag, p.injury_detail,
               p.result, g.home_team, g.away_team, g.home_score, g.away_score,
               p.pick_side
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
            total_bet = picks_df["recommended_bet"].sum()
            st.metric("Total Exposure", f"${total_bet:,.2f}")
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
                    st.caption(f"{row['sport']} | {row['home_team']} vs {row['away_team']}")
                with c2:
                    st.metric("Model %", f"{row['model_probability']:.1%}")
                with c3:
                    st.metric("DK %", f"{row['dk_implied_prob']:.1%}")
                with c4:
                    st.metric("Edge", f"{row['edge']:.1%}")
                with c5:
                    st.metric("Bet", f"${row['recommended_bet']:.0f}")

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
    cutoff = (date.today() - timedelta(days=lookback)).isoformat()

    # ── Running bankroll chart ─────────────────────────────────────────────────
    bankroll_hist = query("""
        SELECT game_date,
               %s + SUM(profit_kelly) OVER (ORDER BY settled_at ROWS UNBOUNDED PRECEDING) as bankroll
        FROM picks
        WHERE game_date >= %s
          AND result IS NOT NULL
          AND signal_type = 'BET'
          AND {_ACTION_FILTER}
        ORDER BY settled_at
    """, (BANKROLL, cutoff))

    if not bankroll_hist.empty:
        fig = px.line(bankroll_hist, x="game_date", y="bankroll",
                      title="Paper Bankroll (Kelly Sizing)",
                      labels={"game_date": "Date", "bankroll": "Bankroll ($)"},
                      line_shape="spline")
        fig.add_hline(y=BANKROLL, line_dash="dash", line_color="gray",
                      annotation_text="Starting Bankroll")
        fig.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                           font_color="white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # ── Win rate and ROI by model ─────────────────────────────────────────────
    model_perf = query("""
        SELECT model_id, sport,
               COUNT(*) as picks,
               ROUND(AVG(CASE WHEN result='WIN' THEN 1.0 ELSE 0.0 END), 3) as win_rate,
               ROUND(SUM(profit_flat) / (COUNT(*) * 100.0), 3) as flat_roi,
               ROUND(AVG(edge), 3) as avg_edge
        FROM picks
        WHERE game_date >= %s
          AND result IS NOT NULL
          AND signal_type = 'BET'
          AND {_ACTION_FILTER}
          AND result IN ('WIN','LOSS')
        GROUP BY model_id, sport
        ORDER BY flat_roi DESC
    """, (cutoff,))

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
            fig3 = px.bar(model_perf, x="model_id", y="flat_roi",
                          color="sport", title="Flat-Bet ROI by Model",
                          labels={"model_id": "", "flat_roi": "ROI (%)"},
                          barmode="group")
            fig3.add_hline(y=0, line_dash="dash", line_color="gray")
            fig3.update_layout(plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                               font_color="white")
            st.plotly_chart(fig3, use_container_width=True)

        st.dataframe(model_perf, use_container_width=True)

    # ── Calibration chart ─────────────────────────────────────────────────────
    cal_df = query("""
        SELECT model_probability, result
        FROM picks
        WHERE game_date >= %s
          AND result IN ('WIN','LOSS')
          AND signal_type = 'BET'
          AND {_ACTION_FILTER}
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
    edge_df = query("""
        SELECT edge, result, sport
        FROM picks
        WHERE game_date >= %s AND signal_type = 'BET' AND result IS NOT NULL
          AND {_ACTION_FILTER}
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
# TAB 4: PAPER TRADING LOG
# ═══════════════════════════════════════════════════════════════════════════════

with tab_log:
    st.header("💰 Paper Trading Log")

    log_lookback = st.slider("Days to show", 1, 90, 14)
    log_cutoff   = (date.today() - timedelta(days=log_lookback)).isoformat()

    log_df = query("""
        SELECT p.game_date, p.sport, p.pick_label, p.model_id,
               p.signal_type, p.confidence_tier,
               p.model_probability, p.dk_implied_prob,
               p.edge, p.dk_odds, p.recommended_bet,
               p.result, p.profit_flat, p.profit_kelly,
               p.injury_flag
        FROM picks p
        WHERE p.game_date >= %s
          AND p.signal_type = 'BET'
          AND {_ACTION_FILTER}
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
        log_df["profit_flat"]       = log_df["profit_flat"].map(lambda x: f"${x:+.2f}" if x is not None else "–")
        log_df["profit_kelly"]      = log_df["profit_kelly"].map(lambda x: f"${x:+.2f}" if x is not None else "–")

        styled = log_df.style.applymap(_style_result, subset=["result"]) \
                             .applymap(_style_signal, subset=["signal_type"])

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
            "BANKROLL":             f"${BANKROLL:,.2f}",
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
