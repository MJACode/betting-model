"""The credit arithmetic behind docs/decision_timing.md's inventory (2026-11-14).

Each count below was measured on 2026-11-14 by the inventory of every model's
decision timing: refresh passes per season from the stored schedule (`games`)
and the worker's pass times (53 a day, docs/cloud_worker.md), held snapshots
from the purchase ledgers (`odds_history_pulls` and the per-sport ledgers),
and per-game counts from `games`. A bulk snapshot bills 10 credits a market
(a `bookmakers=` list of ten books or fewer is one region); a per-game call
bills 10 a market that comes back, so the per-game figures are ceilings.

    python -m scripts.decision_timing_inventory_costs

Prints each model's credits and the totals by sport. No database, no network.
"""
mlb_ticks = {2021:11819,2022:11978,2023:11872,2024:12296,2025:12508,2026:11554}
mlb_held  = {2021:183,2022:183,2023:183,2024:187,2025:186,2026:148}
hs = sum(mlb_ticks[s]-mlb_held[s] for s in mlb_ticks)                       # h2h, spreads
tot = sum(mlb_ticks[s]-(mlb_held[s] if s>=2024 else 0) for s in mlb_ticks)  # totals: none held before 2024
r = {}
r['mlb_moneyline']=hs*10; r['mlb_runline']=hs*10; r['mlb_over_under']=tot*10
r['mlb_f5_moneyline']=56518*10; r['mlb_f5_over_under']=(56477+57020)*10; r['mlb_f5_runline']=(56477+57020)*10
for m in ['batter_runs','batter_walks','batter_hits','batter_tb','batter_sb','pitcher_k','pitcher_hits','pitcher_outs','pitcher_er','pitcher_walks']: r['mlb_prop_'+m]=56518*10
nba_ticks=[8109,9593,9593,9593,9593,9593]; nba_held=[1003,1244,1199,1194,1221,1230]
r['nba_total_luck']=(sum(nba_ticks)-sum(nba_held))*10
nba_ev = 34892+34988+35066-3690
for m in ['nba_first_half_total_luck','nba_team_total_luck','nba_q1_trend','nba_q1_trend_ml']: r[m]=nba_ev*10
r['nba_prop_market']=nba_ev*50; r['nba_prop_projection']=nba_ev*60
nhl_t={2021:9699,2022:14045,2023:13621,2024:14098,2025:13727,2026:13038}; nhl_h={2021:406,2022:618,2023:574,2024:582,2025:586,2026:565}
r['nhl_moneyline']=sum(nhl_t[s]-nhl_h[s] for s in range(2022,2027))*10
r['nhl_over_under']=sum(nhl_t[s]-nhl_h[s] for s in nhl_t)*10
nhl_ev=39780+39024+39434-(1404+1403+1401)
for m in ['nhl_moneyline_regulation','nhl_prop_assists','nhl_prop_blocked_shots','nhl_prop_saves','nhl_prop_shots_on_goal']: r[m]=nhl_ev*10
ncaab_missing=13038+14440+36274+37952+37952+37985
r['ncaab_total_blend']=ncaab_missing*10; r['ncaab_moneyline_first_post']=ncaab_missing*20
fh=(6243+6293+6300)*6; r['ncaab_first_half_spread']=fh*10; r['ncaab_first_half_total']=fh*10
nf={2022:7632,2023:7632-600,2024:8268-108,2025:8268-108}
r['ncaaf_over_under']=sum(nf.values())*10; r['ncaaf_spread (with premium)']=sum(nf[s] for s in (2023,2024,2025))*10; r['ncaaf_moneyline']=sum(nf.values())*10
op_need=21891+22898+41186+45794*3; op_held=501+493+547+554+635+544
r['nfl_opener_spread']=(op_need-op_held)*10
r['nfl_wind_totals']=(5376+5413-(543+546))*10
pp=855*24-914; r['nfl_prop_market']=pp*80; r['nfl extra 4 markets (tackles, rush_att, rush_rec, sacks)']=pp*10*4
r['wnba_moneyline']=(6678+9222)*10; r['wnba_over_under']=9222*10; r['wnba_spread']=9222*10; r['wnba_prop_market']=2002*30
for m in ['assists','rebounds','pra','points','threes']: r['wnba_prop_player_'+m]=8516*10
r['euroleague_h1_dog_ml']=512*10; r['euroleague_q1_club_share_total']=512*20
r['atp_moneyline_shop']=(115328-19221)*10; r['wta_moneyline_shop']=(121489-18157)*10
r['ufc_open_moneyline']=2199*23*10
for k,v in r.items(): print(f"{k:55s} {v:>12,}")
sport = lambda k: ('MLB' if k.startswith('mlb') else 'NBA' if k.startswith('nba') else 'NHL' if k.startswith('nhl') else 'NCAAB' if k.startswith('ncaab_') else 'NCAAF' if k.startswith('ncaaf') else 'NFL' if k.startswith('nfl') else 'WNBA' if k.startswith('wnba') else 'EuroLeague' if k.startswith('euro') else 'Tennis' if k[:3] in ('atp','wta') else 'UFC')
from collections import defaultdict
S=defaultdict(int)
for k,v in r.items():
    if k=='nba_prop_projection': v = nba_ev*90 - nba_ev*50   # union of 9 markets with nba_prop_market
    S[sport(k)]+=v
print('---'); [print(f"{k:12s} {v:>12,}") for k,v in sorted(S.items(), key=lambda x:-x[1])]; print('TOTAL', f"{sum(S.values()):,}")
print('nba props union 9 markets', f"{nba_ev*90:,}", ' nba q1 both markets', f"{nba_ev*20:,}")
print('nba_total_luck lenient', f"{(sum(nba_ticks)-sum(nba_held)-(1133+1330+1322+1292+1316+1323))*10:,}")
print('nfl opener hourly alt', f"{(3649+3817*5-op_held)*10:,}")
print('mlb props 2024-2025 extension each', f"{(56477+57020)*10:,}", 'x10 models', f"{(56477+57020)*100:,}")
print('balance multiple', round(sum(S.values())/1779544,1))
