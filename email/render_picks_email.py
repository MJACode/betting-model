"""Render the daily picks email to a standalone HTML file.

Usage:
    python -m email.render_picks_email          # uses mock data, writes email/preview.html
    python -m email.render_picks_email --live   # pulls today's picks from Supabase (not implemented yet)

The output is a self-contained HTML file with inline CSS that renders correctly
in Gmail, Apple Mail, Outlook, and any modern browser. No external assets.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Pick:
    game_time_et: str
    matchup: str
    pick_label: str
    model_short: str
    model_pct: float
    dk_odds: Optional[str]
    edge_pct: Optional[float]
    confidence: str
    kelly_pct: float
    bet_dollars: float
    weather: str
    injuries: str
    notes: str


MOCK_BANKROLL = 1500.0
MOCK_DATE = "Wednesday, May 20, 2026"

MOCK_PICKS = [
    Pick(
        game_time_et="7:05 PM ET",
        matchup="NYY @ BOS",
        pick_label="Over 9.5 Runs",
        model_short="O/U",
        model_pct=68.7,
        dk_odds="-110",
        edge_pct=15.4,
        confidence="HIGH",
        kelly_pct=3.2,
        bet_dollars=48.00,
        weather="72°F, wind 9 mph (out +5.3)",
        injuries="—",
        notes="—",
    ),
    Pick(
        game_time_et="7:10 PM ET",
        matchup="LAD @ COL",
        pick_label="LAD ML",
        model_short="ML",
        model_pct=73.4,
        dk_odds="-145",
        edge_pct=12.8,
        confidence="HIGH",
        kelly_pct=2.9,
        bet_dollars=43.50,
        weather="68°F, wind 14 mph (out +9.1)",
        injuries="—",
        notes="—",
    ),
    Pick(
        game_time_et="7:40 PM ET",
        matchup="ATL @ CHC",
        pick_label="ATL -1.5",
        model_short="RL",
        model_pct=71.2,
        dk_odds="+118",
        edge_pct=14.6,
        confidence="HIGH",
        kelly_pct=3.7,
        bet_dollars=55.50,
        weather="64°F, wind 11 mph (out -3.2)",
        injuries="CHC: Hoerner Q",
        notes="—",
    ),
    Pick(
        game_time_et="7:40 PM ET",
        matchup="ATL @ CHC",
        pick_label="Spencer Strider Over 6.5 Ks",
        model_short="K Prop",
        model_pct=64.8,
        dk_odds="-118",
        edge_pct=10.6,
        confidence="MED",
        kelly_pct=2.1,
        bet_dollars=31.50,
        weather="64°F, wind 11 mph (out -3.2)",
        injuries="—",
        notes="—",
    ),
    Pick(
        game_time_et="8:10 PM ET",
        matchup="HOU @ TEX",
        pick_label="ATL F5 ML",
        model_short="F5 ML",
        model_pct=64.1,
        dk_odds="N/A",
        edge_pct=7.3,
        confidence="MED",
        kelly_pct=1.8,
        bet_dollars=27.00,
        weather="Dome",
        injuries="—",
        notes="⚠ Borderline (F5 only fetched at 11am — may shift if line moves)",
    ),
    Pick(
        game_time_et="9:40 PM ET",
        matchup="OAK @ SEA",
        pick_label="Aaron Judge Over 0.5 HR",
        model_short="HR Prop",
        model_pct=22.4,
        dk_odds=None,
        edge_pct=None,
        confidence="MED",
        kelly_pct=0.0,
        bet_dollars=0.00,
        weather="61°F, wind 7 mph (out +2.1)",
        injuries="—",
        notes="Prob-only (no DK line)",
    ),
    Pick(
        game_time_et="10:10 PM ET",
        matchup="STL @ SF",
        pick_label="Bobby Witt Jr. Over 1.5 Hits",
        model_short="Hits Prop",
        model_pct=62.9,
        dk_odds="-115",
        edge_pct=9.8,
        confidence="MED",
        kelly_pct=2.0,
        bet_dollars=30.00,
        weather="58°F, wind 12 mph (out -6.4)",
        injuries="—",
        notes="—",
    ),
]


CONFIDENCE_COLOR = {
    "HIGH": "#16a34a",
    "MED": "#ca8a04",
    "LOW": "#dc2626",
}


def _fmt_odds(odds: Optional[str]) -> str:
    if odds is None or odds == "N/A":
        return '<span style="color:#6b7280;">N/A</span>'
    return odds


def _fmt_edge(edge: Optional[float]) -> str:
    if edge is None:
        return '<span style="color:#6b7280;">—</span>'
    sign = "+" if edge >= 0 else ""
    return f"{sign}{edge:.1f}%"


def _pick_card(pick: Pick) -> str:
    conf_color = CONFIDENCE_COLOR.get(pick.confidence, "#6b7280")
    bet_str = f"${pick.bet_dollars:,.2f}" if pick.bet_dollars > 0 else '<span style="color:#6b7280;">—</span>'
    notes_row = ""
    if pick.notes and pick.notes != "—":
        notes_row = f"""
              <tr>
                <td colspan="2" style="padding:8px 16px 12px 16px; font-size:12px; color:#92400e; background:#fef3c7; border-top:1px solid #fde68a;">
                  {pick.notes}
                </td>
              </tr>"""

    injuries_row = ""
    if pick.injuries and pick.injuries != "—":
        injuries_row = f"""
              <tr>
                <td colspan="2" style="padding:6px 16px; font-size:12px; color:#991b1b;">
                  <strong>Injuries:</strong> {pick.injuries}
                </td>
              </tr>"""

    return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0; background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
        <tr>
          <td style="padding:14px 16px 10px 16px; border-bottom:1px solid #f3f4f6;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="font-size:13px; color:#6b7280; font-weight:500;">
                  {pick.game_time_et} · {pick.matchup}
                </td>
                <td align="right" style="font-size:11px; font-weight:700; letter-spacing:0.5px; color:{conf_color};">
                  {pick.confidence}
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding-top:4px; font-size:17px; font-weight:600; color:#111827;">
                  {pick.pick_label}
                </td>
              </tr>
              <tr>
                <td colspan="2" style="padding-top:2px; font-size:12px; color:#9ca3af; text-transform:uppercase; letter-spacing:0.5px;">
                  {pick.model_short}
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 16px; background:#f9fafb;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size:13px; color:#374151;">
              <tr>
                <td width="25%" style="padding:4px 0;"><span style="color:#6b7280;">Model</span><br/><strong style="color:#111827; font-size:15px;">{pick.model_pct:.1f}%</strong></td>
                <td width="25%" style="padding:4px 0;"><span style="color:#6b7280;">DK Odds</span><br/><strong style="color:#111827; font-size:15px;">{_fmt_odds(pick.dk_odds)}</strong></td>
                <td width="25%" style="padding:4px 0;"><span style="color:#6b7280;">Edge</span><br/><strong style="color:#16a34a; font-size:15px;">{_fmt_edge(pick.edge_pct)}</strong></td>
                <td width="25%" style="padding:4px 0;"><span style="color:#6b7280;">Bet</span><br/><strong style="color:#111827; font-size:15px;">{bet_str}</strong> <span style="color:#9ca3af; font-size:12px;">({pick.kelly_pct:.1f}%)</span></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 16px; font-size:12px; color:#6b7280; border-top:1px solid #f3f4f6;">
            <strong style="color:#374151;">Weather:</strong> {pick.weather}
          </td>
        </tr>{injuries_row}{notes_row}
      </table>"""


def render_email(picks: list[Pick], bankroll: float, date_str: str) -> str:
    total_exposure = sum(p.bet_dollars for p in picks)
    exposure_pct = (total_exposure / bankroll) * 100 if bankroll > 0 else 0
    bet_count = sum(1 for p in picks if p.bet_dollars > 0)
    borderline_count = sum(1 for p in picks if "Borderline" in p.notes)

    cards_html = "\n".join(_pick_card(p) for p in picks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Picks — {date_str}</title>
</head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%;">

          <!-- Header -->
          <tr>
            <td style="padding:0 0 20px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%); border-radius:8px;">
                <tr>
                  <td style="padding:24px 20px;">
                    <div style="font-size:11px; color:#94a3b8; letter-spacing:2px; font-weight:600;">BETTING MODEL · DAILY PICKS</div>
                    <div style="font-size:22px; color:#ffffff; font-weight:700; padding-top:6px;">{date_str}</div>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px; padding-top:14px; border-top:1px solid #334155;">
                      <tr>
                        <td width="33%">
                          <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Bankroll</div>
                          <div style="font-size:18px; color:#ffffff; font-weight:600; padding-top:2px;">${bankroll:,.0f}</div>
                        </td>
                        <td width="33%">
                          <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Picks</div>
                          <div style="font-size:18px; color:#ffffff; font-weight:600; padding-top:2px;">{bet_count}</div>
                        </td>
                        <td width="33%">
                          <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Exposure</div>
                          <div style="font-size:18px; color:#ffffff; font-weight:600; padding-top:2px;">${total_exposure:,.2f} <span style="font-size:12px; color:#94a3b8; font-weight:400;">({exposure_pct:.1f}%)</span></div>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Picks -->
          <tr>
            <td>
              {cards_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 16px; background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; margin-top:8px;">
              <div style="font-size:13px; color:#374151; line-height:1.6;">
                <strong>Reminder:</strong> Picks may flip to AVOID on later refreshes — re-query before placing bets.
                F5 picks are fetched once at 11am and do not refresh.
                {f'<br/><br/><span style="color:#92400e;"><strong>⚠ {borderline_count} borderline F5 pick(s)</strong> — verify before placing.</span>' if borderline_count else ''}
              </div>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:20px 0 0 0; font-size:11px; color:#9ca3af;">
              Paper trading · Not real money · Sent {datetime.now().strftime('%I:%M %p ET').lstrip('0')}
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "preview.html")
    args = parser.parse_args()

    html = render_email(MOCK_PICKS, MOCK_BANKROLL, MOCK_DATE)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out} ({len(html):,} bytes, {len(MOCK_PICKS)} picks)")


if __name__ == "__main__":
    main()
