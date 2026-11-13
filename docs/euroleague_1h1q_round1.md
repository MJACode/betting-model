# EuroLeague first half and first quarter: research round 1

2026-11-13. Every number below was printed by a script in
`scripts/euroleague_research/` (named above each table) reading only the local
parquet cache (`C:\Users\micha\euroleague_research\cache`, a copy of
Supabase) and, for full-game lines, the purchase spool for 2025-26 only. No
database, no API call, no repo file edited.

**Conventions.** Results in units. Every bet sized to win 1 unit, risk capped
at 3 (a price p < 0 risks min(|p|/100, 3); p > 0 risks 1 to win p/100), graded
at the book's quoted price. Return = units won / units risked on graded
(non-push) bets. Intervals are 90%, resampling game dates (1,000 draws).
Seasons use the ending year: 2024 = 2023-24, 2025 = 2024-25, 2026 = 2025-26,
2027 = 2026-27 to date (107 played games). First half = quarters 1+2, first
quarter = quarter 1; overtime never counts. "Decidable" books (a pick may name
them): FanDuel, BetMGM, BetRivers, Fanatics (DraftKings quoted none). BetUS,
GTbets and MyBookie are offshore references only, marked "(ref)", never a book
a pick could name.

**Frozen before any result was read** (header of `r1_lib.py`): the six main
markets; decision marks T-10 (the close) and each game's earliest mark; the
off-centre rule (a main spread or total whose no-vig side probability is
outside 35-65% is set aside); best price = the best decidable price on the
modal decidable number (the repo's same-line rule); the method's cut grid
0.00-0.05 with the catalogued cut 0.02, decided at T-10, other read T-60. The
structural rule's thresholds (1.0 / 1.5 / 2.0 points) are fixed in
`r1_structure.py`'s header, written before that script first ran. The
off-centre rule was set after reading the price ranges (`r1_facts.py`) and
before any return was graded.

## Verdict in one paragraph

Nothing clears. The first-half and first-quarter two-way moneylines are
draw-no-bet (a tied period pushes), measured. Decidable books exist only from
2025-26, so every bettable table rests on about 423 games (2025-26 plus
2026-27 to date), which resolves a return to roughly +/-8 points. No blind
baseline is positive once 556 cells are corrected for multiplicity (0 of 103
positive cells with 25+ bets survive). The books price the first half at a
near-constant 50.2% of the full-game total and the first quarter at 25.1%, and
their period numbers sit within about half a point of that straight line, so
the full-game-to-half method can only disagree with them through its own
fitted slope. Run unchanged on the 2025-26 time split it shows one positive
(first-half totals, 51 bets, +29.8%), which comes from a slope that held in
2025-26 and failed when frozen and read on 2023-24 and 2026-27. A walk-forward
version on a sharp full-game anchor shows one lead (first-quarter unders, 59
bets, +15.0%, interval -5.5 to +33.0) that passes the placebo and the
market-alone control but fails the side split (57 of 59 unders), the
best-dates test, and rests on one season. Two data-quality problems were found in the
stored main numbers of BetMGM (2026-27) and Fanatics (2025-26).

## 1. Settlement

**The two-way first-half and first-quarter moneylines push on a tie.** No
two-way quote at any book carries a draw price; the three-way markets
(BetRivers, Fanatics) do. At BetRivers, on the same fetch, the two-way price
de-vigged equals the three-way price with the draw removed (draw no bet):
median difference 0.0000, mean absolute 0.0012 over 2,461 first-half pairs
(0.0046 first quarter). Had a tie lost the two-way bet, the two-way fair price
would match the three-way win price instead, and it is +0.028 (first half) and
+0.033 (first quarter) away from it. Measured at BetRivers only; the other
books' two-way raw margins (1.05-1.09) are what a push market carries, not what
a tie-loses market would (about 1.01-1.02 at the same vig). **Fanatics has no
two-way first-half moneyline at all**, only the three-way, where a tie loses: a
different bet. Ties are common: the first quarter ended level in 134 of 2,125
played games (6.31%; 3.7-8.2% a season), the first half in 72 (3.39%). Spreads
and totals push on whole numbers (about 22% of first-half main numbers are
whole; first-quarter numbers almost never are). The grading code asserts the
spread sign and the tie push on every import (`r1_lib._assert_settlement`).

Printed by `scripts/euroleague_research/r1_settle2.py`:

```
== h2h_h1 vs h2h_3_way_h1 at betrivers: 2461 paired (game, mark) quotes
   two-way raw sum median 1.0651; three-way raw sum median 1.1034; three-way fair draw median 0.0476
   two-way home implied minus three-way home implied: median +0.0073, share > 0: 0.983
   two-way fair home minus three-way draw-no-bet home: median +0.0000, mean abs 0.0012
   two-way fair home minus three-way fair home WIN:    median +0.0283, mean abs 0.0273
h2h_h1 h2h_3_way_h1 fanatics no paired quotes
== h2h_q1 vs h2h_3_way_q1 at betrivers: 2461 paired (game, mark) quotes
   two-way raw sum median 1.0652; three-way raw sum median 1.1034; three-way fair draw median 0.0646
   two-way home implied minus three-way home implied: median +0.0164, share > 0: 0.937
   two-way fair home minus three-way draw-no-bet home: median -0.0004, mean abs 0.0046
   two-way fair home minus three-way fair home WIN:    median +0.0333, mean abs 0.0336
h2h_q1 h2h_3_way_q1 fanatics no paired quotes
```

Printed by `scripts/euroleague_research/r1_settle.py`:

```
== quotes by season and market (rows) ==
season        2024  2025   2026  2027
market                               
h2h_3_way_h1     0     0   3322    10
h2h_3_way_q1     0     0   2461     0
h2h_h1        1696  3332  12505  4564
h2h_q1        1618   444   2509  1674
spreads_h1    2190  4226  11448  4686
spreads_q1    2047  1434   5566  2528
totals_h1     2194  4235  11441  4706
totals_q1     2050  1437   4550  1781

== draw_price presence, by market and book ==
-- h2h_h1
            rows  with_draw  home_na
bookmaker                           
betmgm      3680          0        0
betrivers   3306          0        0
betus       4661          0        0
fanduel     3151          0        0
gtbets      6259          0        0
mybookieag  1040          0        0
-- h2h_q1
           rows  with_draw  home_na
bookmaker                          
betmgm      853          0        0
betrivers  3306          0        0
betus      2086          0        0
-- h2h_3_way_h1
           rows  with_draw  home_na
bookmaker                          
betrivers  2461       2461        0
fanatics    871        871        0
-- h2h_3_way_q1
           rows  with_draw  home_na
bookmaker                          
betrivers  2461       2461        0
-- h2h_h2
           rows  with_draw  home_na
bookmaker                          
betrivers  2461          0        0
fanduel     150          0        0
-- h2h_q2
           rows  with_draw  home_na
bookmaker                          
betrivers  1429          0        0

== two-way overround (home + away implied) by market and book, median ==
-- h2h_h1
               ovr    ovr3
bookmaker                 
betmgm      1.0905  1.0905
betrivers   1.0667  1.0667
betus       1.0738  1.0738
fanduel     1.0600  1.0600
gtbets      1.0700  1.0700
mybookieag  1.0506  1.0506
-- h2h_q1
              ovr    ovr3
bookmaker                
betmgm     1.0916  1.0916
betrivers  1.0667  1.0667
betus      1.0730  1.0730
-- h2h_3_way_h1
              ovr    ovr3
bookmaker                
betrivers  1.0518  1.1034
fanatics   1.0426  1.0901
-- h2h_3_way_q1
              ovr    ovr3
bookmaker                
betrivers  1.0338  1.1034

== ties in the stored period scores ==
        games  q1_tie  h1_tie  q1_tie_pct  h1_tie_pct
season                                               
2021      328      19       9        5.79        2.74
2022      299      21      18        7.02        6.02
2023      328      26       6        7.93        1.83
2024      331      27      12        8.16        3.63
2025      330      18      11        5.45        3.33
2026      402      19      12        4.73        2.99
2027      107       4       4        3.74        3.74
pooled 2125 q1 ties 134 6.31 % | h1 ties 72 3.39 %

== main-market shape: rows per (game, market, book, mark) ==
spreads_h1 groups 22550 rows/group dist {1: 22550} | no mark 0
totals_h1 groups 22576 rows/group dist {1: 22576} | no mark 0
h2h_h1 groups 22097 rows/group dist {1: 22097} | no mark 0
spreads_q1 groups 11575 rows/group dist {1: 11575} | no mark 0
totals_q1 groups 9818 rows/group dist {1: 9818} | no mark 0
h2h_q1 groups 6245 rows/group dist {1: 6245} | no mark 0

== quotes per (game, market, book): distinct marks / distinct numbers ==
spreads_h1 marks per game-book {1: 23, 2: 18, 3: 28, 4: 42, 5: 96, 6: 199, 7: 771, 8: 1896}
spreads_h1 numbers per game-book {1: 1621, 2: 1146, 3: 264, 4: 39, 5: 3}
totals_h1 marks per game-book {1: 22, 2: 19, 3: 27, 4: 39, 5: 96, 6: 198, 7: 781, 8: 1893}
totals_h1 numbers per game-book {1: 1340, 2: 1146, 3: 476, 4: 95, 5: 17, 6: 1}

== snapshot_at vs commence_time: minutes before tip (main markets) ==
mark              T-10   T-120  T-1440   T-180    T-30   T-360    T-60   T-720
lead     count  8992.0  8967.0  5913.0  8897.0  8993.0  8616.0  8985.0  7860.0
         mean     14.9   124.9  1444.9   184.9    34.9   364.9    64.9   725.0
         std       1.8     0.6     1.0     0.5     1.1     0.5     0.6     1.4
         min      13.6   123.8  1443.5   183.8    33.7   363.8    63.7   723.8
         5%       14.2   124.2  1444.1   184.2    34.2   364.2    64.2   724.2
         50%      14.8   124.8  1444.8   184.8    34.8   364.9    64.8   724.9
         95%      15.7   125.7  1445.7   185.7    35.7   365.9    65.6   726.0
         max      72.6   135.9  1481.3   196.8    72.6   372.1    77.7   771.3
ask_lead count  8992.0  8967.0  5913.0  8897.0  8993.0  8616.0  8985.0  7860.0
         mean     10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
         std       0.0     0.0     0.0     0.0     0.0     0.0     0.0     0.0
         min      10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
         5%       10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
         50%      10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
         95%      10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
         max      10.0   120.0  1440.0   180.0    30.0   360.0    60.0   720.0
snap after tip: 0 | snap after ask: 0
```

## 2. Data facts that shape every table

**Stored "main" numbers that are ladder rungs.** Many BetMGM 2026-27 and
Fanatics 2025-26 "main" quotes sit 4-8 points from every other book at long
prices (-550/+310). No `spreads_h1_alternate` or `totals_h1_alternate` market
exists in the cache, so the feed returned one number for those books and it was
stored as the main. Off-centre quotes (no-vig side outside 35-65%) were set
aside from every main-line table: BetMGM 2026-27 440 first-half spread rows (66
games), 694 first-half total rows (96 games), 794 first-quarter spread rows
(101 games), 829 first-quarter total rows (104 games); Fanatics 2025-26 127 and 111 rows (36 and 30 games). **Even the quotes
that passed that filter are rungs**: every on-centre BetMGM 2026-27 quote is 1+
points from the other books' median (median 3-5 points), and 79-85% of
Fanatics' 2025-26 ones are (`r1_nbooks.py`, table 2). Read every BetMGM
2026-27 and Fanatics 2025-26 per-book cell as a bet on a rung, not on the main
line. This looks like a main-number selection problem in the period purchase
for those two books (flagged, not investigated: no repo edits this round).
BetRivers' first-half spreads and totals hold 3 games in 2025-26 (its
moneyline holds 316); FanDuel's first-quarter totals in 2026-27 hold only the
T-10 mark.

Printed by `scripts/euroleague_research/r1_facts2.py`:

```
== spreads_h1: share of main quotes with a side's no-vig prob beyond 0.35/0.65, by book and season
season      2024  2025   2026   2027
bookmaker                           
betmgm       NaN   NaN  0.004  0.531
betrivers    NaN   NaN  0.000  0.000
betus        0.0   0.0  0.000  0.000
fanatics     NaN   NaN  0.273    NaN
fanduel      NaN   NaN  0.000  0.000
gtbets       NaN   0.0  0.000  0.000
mybookieag   NaN   NaN  0.000  0.000
-- off-centre quotes: their number minus the (game, mark) median number, by book
           count  mean   std  min  25%  50%  75%  max
bookmaker                                            
betmgm     450.0 -5.17  1.83 -9.0 -6.0 -5.0 -4.5  6.0
fanatics   127.0 -2.19  4.11 -6.0 -5.0 -4.0  4.0  5.5
                     game_id   mark bookmaker  spread_home  home_price  away_price  med
137599  EUROLEAGUE_E2025_101  T-120  fanatics         -3.5       170.0      -240.0  0.5
137604  EUROLEAGUE_E2025_101   T-30  fanatics         -3.5       170.0      -240.0  0.5
137609  EUROLEAGUE_E2025_101   T-60  fanatics         -3.5       170.0      -240.0  0.5
137614  EUROLEAGUE_E2025_101   T-10  fanatics         -3.5       170.0      -240.0  0.5
138705  EUROLEAGUE_E2025_102  T-120  fanatics          1.5      -240.0       170.0 -2.5
138710  EUROLEAGUE_E2025_102   T-60  fanatics          1.5      -240.0       170.0 -2.5
138720  EUROLEAGUE_E2025_102   T-30  fanatics          1.5      -240.0       170.0 -2.5
138725  EUROLEAGUE_E2025_102   T-10  fanatics          1.5      -240.0       170.0 -2.5

== totals_h1: share of main quotes with a side's no-vig prob beyond 0.35/0.65, by book and season
season      2024  2025   2026   2027
bookmaker                           
betmgm       NaN   NaN  0.010  0.837
betrivers    NaN   NaN    NaN  0.000
betus        0.0   0.0  0.000  0.000
fanatics     NaN   NaN  0.238    NaN
fanduel      NaN   NaN  0.000  0.000
gtbets       NaN   0.0  0.000  0.000
mybookieag   NaN   NaN  0.000  0.000
-- off-centre quotes: their number minus the (game, mark) median number, by book
           count  mean   std  min   25%  50%   75%   max
bookmaker                                               
betmgm     718.0  7.68  1.52  4.0  6.75  7.5  8.25  14.0
fanatics   111.0 -1.18  4.85 -6.0 -5.00 -5.0  5.00   5.5
                     game_id   mark bookmaker  total_line  over_price  under_price   med
136642  EUROLEAGUE_E2025_100  T-120  fanatics        75.5      -260.0        185.0  80.5
136647  EUROLEAGUE_E2025_100   T-60  fanatics        75.5      -260.0        185.0  80.5
136652  EUROLEAGUE_E2025_100   T-10  fanatics        75.5      -260.0        185.0  80.5
136657  EUROLEAGUE_E2025_100   T-30  fanatics        75.5      -260.0        185.0  80.5
140024  EUROLEAGUE_E2025_103  T-120  fanatics        97.5       175.0       -250.0  92.5
140029  EUROLEAGUE_E2025_103   T-60  fanatics        97.5       175.0       -250.0  92.5
140034  EUROLEAGUE_E2025_103   T-30  fanatics        97.5       175.0       -250.0  92.5
140039  EUROLEAGUE_E2025_103   T-10  fanatics        97.5       175.0       -250.0  92.5

== totals_q1: share of main quotes with a side's no-vig prob beyond 0.35/0.65, by book and season
season     2024  2025   2026  2027
bookmaker                         
betmgm      NaN   NaN  0.013   1.0
betrivers   NaN   NaN    NaN   0.0
betus       0.0   0.0  0.000   NaN
fanatics    NaN   NaN  0.000   NaN
fanduel     NaN   NaN  0.000   0.0
-- off-centre quotes: their number minus the (game, mark) median number, by book
           count  mean   std  min  25%  50%  75%   max
bookmaker                                             
betmgm     853.0  3.95  1.49  0.0  3.5  4.0  4.0  10.0
                     game_id    mark bookmaker  total_line  over_price  under_price   med
450838  EUROLEAGUE_E2025_404   T-360    betmgm        50.5       375.0       -700.0  50.5
450839  EUROLEAGUE_E2025_404   T-720    betmgm        50.5       400.0       -800.0  50.5
450840  EUROLEAGUE_E2025_404   T-180    betmgm        50.5       375.0       -700.0  50.5
450841  EUROLEAGUE_E2025_404   T-120    betmgm        50.5       375.0       -700.0  50.5
450842  EUROLEAGUE_E2025_404    T-60    betmgm        50.5       375.0       -700.0  50.5
450843  EUROLEAGUE_E2025_404    T-30    betmgm        50.5       375.0       -700.0  50.5
450844  EUROLEAGUE_E2025_404    T-10    betmgm        50.5       375.0       -700.0  45.5
450846  EUROLEAGUE_E2025_404  T-1440    betmgm        50.5       400.0       -800.0  50.5
```

Printed by `scripts/euroleague_research/r1_facts.py`:

```
== Pinnacle: markets it holds ==
season              2024   2025   2026  2027
market                                      
alternate_spreads  25290  28831  34881  9405
alternate_totals   25290  28831  34881  9405

== main-line prices by market and book: quantiles of each side's price ==
-- spreads_h1
              count   mean    std    min  ...    50%    75%    95%    max
bookmaker                                 ...                            
betmgm       6690.0  -99.0  119.0 -550.0  ... -120.0 -110.0  170.0  310.0
betrivers    1738.0 -109.0   52.0 -165.0  ... -120.0 -113.0  100.0  115.0
betus       14522.0 -118.0    4.0 -140.0  ... -120.0 -117.0 -110.0  100.0
fanatics      932.0  -40.0  173.0 -325.0  ... -115.0  135.0  200.0  235.0
fanduel      6718.0 -113.0    8.0 -136.0  ... -113.0 -108.0 -104.0  106.0
gtbets      12420.0 -113.0   24.0 -146.0  ... -115.0 -112.0 -109.0  110.0
mybookieag   2080.0 -117.0    4.0 -128.0  ... -118.0 -114.0 -111.0 -108.0

[7 rows x 10 columns]
-- totals_h1
              count   mean    std    min  ...    50%    75%    95%    max
bookmaker                                 ...                            
betmgm       6690.0 -105.0  141.0 -900.0  ... -120.0 -110.0  210.0  425.0
betrivers    1690.0 -115.0   35.0 -162.0  ... -120.0 -114.0 -104.0  114.0
betus       14602.0 -118.0    6.0 -140.0  ... -120.0 -118.0 -111.0  100.0
fanatics      932.0  -38.0  166.0 -275.0  ... -115.0  125.0  185.0  200.0
fanduel      6734.0 -113.0    5.0 -122.0  ... -113.0 -111.0 -104.0 -104.0
gtbets      12424.0 -115.0    4.0 -132.0  ... -115.0 -114.0 -109.0 -101.0
mybookieag   2080.0 -117.0    3.0 -127.0  ... -118.0 -115.0 -113.0 -109.0

[7 rows x 10 columns]
-- h2h_h1
              count  mean    std     min  ...    50%    75%    95%    max
bookmaker                                 ...                            
betmgm       7360.0 -51.0  171.0  -625.0  ... -120.0  125.0  180.0  400.0
betrivers    6612.0 -46.0  206.0 -1000.0  ... -115.0  140.0  245.0  540.0
betus        9322.0 -46.0  196.0 -1100.0  ... -120.0  148.0  210.0  550.0
fanduel      6302.0 -40.0  196.0  -720.0  ... -113.0  142.0  235.0  450.0
gtbets      12518.0 -45.0  185.0  -831.0  ... -115.0  138.0  210.0  464.0
mybookieag   2080.0 -41.0  186.0  -625.0  ... -114.0  136.0  226.0  410.0

[6 rows x 10 columns]
-- spreads_q1
            count   mean    std    min  ...    50%    75%    95%    max
bookmaker                               ...                            
betmgm     6690.0  -88.0  162.0 -650.0  ... -120.0 -105.0  225.0  350.0
betrivers  1738.0 -115.0   35.0 -165.0  ... -120.0 -112.0 -106.0  118.0
betus      7072.0 -118.0   16.0 -175.0  ... -120.0 -120.0 -115.0  135.0
fanatics    932.0  -34.0  146.0 -210.0  ... -115.0  125.0  150.0  155.0
fanduel    6718.0  -98.0   58.0 -128.0  ... -113.0 -106.0  100.0  100.0

[5 rows x 10 columns]
-- totals_q1
            count   mean    std     min  ...    50%    75%    95%    max
bookmaker                                ...                            
betmgm     5248.0 -116.0  247.0 -2000.0  ... -120.0 -105.0  320.0  625.0
betrivers  1690.0 -116.0   30.0  -155.0  ... -120.0 -113.0 -106.0  108.0
betus      7084.0 -119.0    7.0  -145.0  ... -120.0 -120.0 -115.0  105.0
fanatics    932.0  -34.0  143.0  -200.0  ... -115.0  121.0  150.0  150.0
fanduel    4682.0 -108.0   36.0  -128.0  ... -113.0 -106.0 -102.0  100.0

[5 rows x 10 columns]
-- h2h_q1
            count  mean    std    min     5%    25%    50%    75%    95%    max
bookmaker                                                                      
betmgm     1706.0 -54.0  140.0 -300.0 -210.0 -160.0 -120.0  110.0  140.0  200.0
betrivers  6612.0 -44.0  154.0 -420.0 -240.0 -162.0 -115.0  120.0  175.0  290.0
betus      4172.0 -49.0  152.0 -560.0 -225.0 -165.0 -120.0  125.0  165.0  330.0

== main numbers: half-point vs whole number share, by market ==
spreads_h1 rows 22550 whole-number share 0.216 | range -11.5 7.5
totals_h1 rows 22576 whole-number share 0.23 | range 75.0 100.5
spreads_q1 rows 11575 whole-number share 0.003 | range -9.5 4.5
totals_q1 rows 9818 whole-number share 0.002 | range 37.5 54.5

== quotes on games not played / without scores ==
season  played
2024    True      329
2025    True      330
2026    True      402
2027    True      107
Name: game_id, dtype: int64
```

**A sharp full-game anchor exists for every season.** Pinnacle's full-game
alternate ladders were bought in the same per-event fetch as the period quote,
at every mark: 8,957 (game, mark) ladders on 291, 330, 402 and 107 games, 11
rungs half a point apart, and 100% of them bracket even money. The fair number
is where the ladder's no-vig probability crosses 50%. In 2025-26 it matches the
five-book US consensus read from the spool at the same mark: median difference
0.0, SD 0.49 points on totals and 0.46 on spreads (3,171 pairs). Pinnacle
prices no first-half or first-quarter line, so a sharp-against-soft read of the
periods themselves is not possible from what was bought.

Printed by `scripts/euroleague_research/r1_pinnacle_ladder.py`:

```
== Pinnacle alternate_totals: (game, mark) ladders
        ladders  games  med_rungs  brackets
season                                     
2024       2310    291       11.0       1.0
2025       2621    330       11.0       1.0
2026       3171    402       11.0       1.0
2027        855    107       11.0       1.0
mark        T-10   T-120  T-1440   T-180    T-30   T-360    T-60   T-720
ladders   1130.0  1130.0  1058.0  1130.0  1130.0  1130.0  1130.0  1119.0
brackets     1.0     1.0     1.0     1.0     1.0     1.0     1.0     1.0
nearest rung |p-0.5| quantiles {0.5: 0.0023, 0.9: 0.0067, 0.99: 0.0069}
rung spacing value counts {0.5: 89330, 1.0: 120}

== Pinnacle alternate_spreads: (game, mark) ladders
        ladders  games  med_rungs  brackets
season                                     
2024       2310    291       11.0       1.0
2025       2621    330       11.0       1.0
2026       3171    402       11.0       1.0
2027        855    107       11.0       1.0
mark        T-10   T-120  T-1440   T-180    T-30   T-360    T-60   T-720
ladders   1130.0  1130.0  1058.0  1130.0  1130.0  1130.0  1130.0  1119.0
brackets     1.0     1.0     1.0     1.0     1.0     1.0     1.0     1.0
nearest rung |p-0.5| quantiles {0.5: 0.0046, 0.9: 0.0092, 0.99: 0.0133}
rung spacing value counts {0.5: 86586, 2.0: 2744, 1.0: 112, 2.5: 8}

alternate_totals season     2024  2025  2026  2027
bookmaker                        
betmgm        0     0   316   104
betrivers     0     0     2    59
pinnacle    291   330   402   107
alternate_spreads season     2024  2025  2026  2027
bookmaker                        
betmgm        0     0   286    94
betrivers     0     0   316   107
fanatics      0     0   316   107
pinnacle    291   330   402   107
team_totals_home season      2026  2027
bookmaker             
betmgm         3    92
betrivers    316   107
fanatics     259    86
mybookieag    80     0
team_totals_away season      2026  2027
bookmaker             
betmgm         3    92
betrivers    316   107
fanatics     259    86
mybookieag    80     0
```

**The 2025-26 full-game consensus (the spool).** 25,904 snapshot files read
for 2025-09-01 to 2026-05-31; all 3,216 (game, mark) pairs found with a median
of 5 US books; every feed name mapped; no event had its home and away swapped
against EuroLeague. At T-10 the full-game snapshot was read a median 14.4
minutes before the tip; the period quotes at T-10 were last updated a median
14.8 minutes before it (5-95%: 14.2-15.7), about 4.8 minutes before each ask.
That stored time moves in lockstep across every book (SD under 2 minutes at
every mark), so it reads as the feed's snapshot time rather than each book's
own last update (flagged, not checked against the raw feed).

Printed by `scripts/euroleague_research/r1_fullgame.py`:

```
Pinnacle ladder fair numbers: 8957 (game, mark) rows; totals found 8957 spreads found 8957
spool files 2025-09-01..2026-05-31: 25904
unmapped feed names: none
2025-26 (game, mark) rows: 3216 | with a US-book full-game total: 3216 | spread: 3216 | feed swapped home/away: 0
        rows  total_us  n_books_med     lead_med     lead_max
mark                                                         
T-1440   402       402          5.0  1444.383333  1454.383333
T-720    402       402          5.0   729.358333   759.383333
T-360    402       402          5.0   369.366667   374.383333
T-180    402       402          5.0   189.350000   194.383333
T-120    402       402          5.0   124.383333   134.383333
T-60     402       402          5.0    64.383333    74.383333
T-30     402       402          5.0    34.366667    34.383333
T-10     402       402          5.0    14.366667    14.383333
US-book full-game total minus Pinnacle ladder fair total (same mark), 2025-26: {'count': 3171.0, 'mean': 0.036, 'std': 0.489, 'min': -1.583, '25%': -0.25, '50%': 0.0, '75%': 0.333, 'max': 1.714}
US-book home spread minus Pinnacle ladder fair spread: {'count': 3171.0, 'mean': -0.002, 'std': 0.464, 'min': -2.296, '25%': -0.289, '50%': 0.0, '75%': 0.264, 'max': 3.033}
Pinnacle main total (spool) minus Pinnacle ladder fair total (cache): {'count': 3169.0, 'mean': -0.042, 'std': 0.425, 'min': -2.0, '25%': -0.333, '50%': -0.071, '75%': 0.232, 'max': 2.0}
```

## 3. Coverage (task 1)

Games with an on-centre main quote, by season, book and mark. **No decidable
book quoted a period line before 2025-26**: 2023-24 is BetUS only, 2024-25
BetUS and GTbets. In 2025-26 FanDuel and BetMGM carry the first-half spread
and total (about 314 of 402 games), BetRivers the first-half and first-quarter
moneyline (316); in 2026-27 FanDuel and BetRivers carry every market on nearly
every game, except that FanDuel posts no first-quarter moneyline and its
first-quarter total only at T-10.

Printed by `scripts/euroleague_research/r1_coverage.py`:

```
played games by season: {2021: 328, 2022: 299, 2023: 328, 2024: 331, 2025: 330, 2026: 402, 2027: 107}
seasons with any main period quote: {2024: 321, 2025: 321, 2026: 402, 2027: 107}

==== spreads_h1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           59    275    293    299    310   315   319   320     331
     betus              59    275    293    299    310   315   319   320     331
2025 ANY BOOK          280    307    312    317    319   318   319   320     330
     betus              44    213    265    289    297   298   297   299     330
     gtbets            276    278    280    280    278   277   277   278     330
2026 ANY BOOK          401    402    402    402    402   402   402   402     402
     ANY DECIDABLE     312    316    316    316    316   316   316   316     402
     betmgm            308    315    316    310    315   314   314   314     402
     betrivers           3      3      3      3      3     3     3     3     402
     betus              46    238    301    346    354   363   367   366     402
     fanatics           59     58     58     58     26    27    27    26     402
     fanduel           310    314    314    314    314   313   313   313     402
     gtbets            401    401    402    401    402   402   402   402     402
     mybookieag          0      4     79     66     59    50    44    41     402
2027 ANY BOOK          107    107    107    107    107   107   107   107     107
     ANY DECIDABLE     107    107    107    107    107   107   107   107     107
     betmgm             46     50     48     50     50    49    49    47     107
     betrivers          99    105    107    107    107   107   107   106     107
     betus               7     77     92    102    102   102   103   103     107
     fanduel           107    107    105    107    107   107   107   107     107
     gtbets             97     96     97     96     96    97    97    97     107
     mybookieag          0     97    100    100    100   100   100   100     107
-- off-centre main quotes set aside (spreads_h1): rows, games, by season and book
                  rows  games
season bookmaker             
2026   betmgm       10      3
       fanatics    127     36
2027   betmgm      440     66

==== totals_h1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           58    277    293    299    310   316   320   321     331
     betus              58    277    293    299    310   316   320   321     331
2025 ANY BOOK          280    306    311    317    319   318   320   320     330
     betus              43    213    264    289    297   300   300   301     330
     gtbets            276    277    281    281    279   278   278   278     330
2026 ANY BOOK          401    402    402    402    402   402   402   402     402
     ANY DECIDABLE     312    316    316    316    316   316   316   316     402
     betmgm            306    313    313    309    313   312   313   313     402
     betus              46    238    302    348    356   363   368   368     402
     fanatics           59     58     58     58     33    31    29    29     402
     fanduel           311    315    315    315    315   314   314   314     402
     gtbets            401    401    402    402    402   402   402   402     402
     mybookieag          0      4     79     66     59    50    44    41     402
2027 ANY BOOK          107    107    107    107    107   107   107   107     107
     ANY DECIDABLE     107    107    107    107    107   107   107   107     107
     betmgm             10     14     15     17     17    20    20    22     107
     betrivers          99    105    107    107    107   107   107   106     107
     betus               7     79     95    106    106   106   106   106     107
     fanduel           107    107    105    107    107   107   107   107     107
     gtbets             97     97     96     96     96    96    96    96     107
     mybookieag          0     97    100    100    100   100   100   100     107
-- off-centre main quotes set aside (totals_h1): rows, games, by season and book
                  rows  games
season bookmaker             
2026   betmgm       24      3
       fanatics    111     30
2027   betmgm      694     96

==== h2h_h1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           53    130    210    247    257   267   267   265     331
     betus              53    130    210    247    257   267   267   265     331
2025 ANY BOOK          285    287    292    302    304   304   306   308     330
     betus              18     34    105    167    172   180   188   195     330
     gtbets            284    284    284    284    284   284   284   285     330
2026 ANY BOOK          401    402    402    402    402   402   402   402     402
     ANY DECIDABLE     353    358    358    358    358   358   358   358     402
     betmgm            350    357    357    353    357   356   356   356     402
     betrivers         253    312    316    316    316   316   316   316     402
     betus              20    113    155    199    213   217   217   218     402
     fanduel           285    287    288    288    288   287   287   287     402
     gtbets            400    401    400    402    401   402   402   402     402
     mybookieag          0      4     79     66     59    50    44    41     402
2027 ANY BOOK          107    107    107    107    107   107   107   107     107
     ANY DECIDABLE     107    107    107    107    107   107   107   107     107
     betmgm            104    104    105    105    105   105   105   105     107
     betrivers          99    105    107    107    107   107   107   106     107
     betus               7     56     77     85     83    83    82    81     107
     fanduel           107    107    105    107    107   107   107   107     107
     gtbets             97     97     97     97     97    97    97    97     107
     mybookieag          0     97    100    100    100   100   100   100     107

==== spreads_q1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           36    211    268    290    303   310   313   316     331
     betus              36    211    268    290    303   310   313   316     331
2025 ANY BOOK           12     87    166    215    230   236   243   245     330
     betus              12     87    166    215    230   236   243   245     330
2026 ANY BOOK          312    316    321    326    326   326   326   326     402
     ANY DECIDABLE     312    316    316    316    316   316   316   316     402
     betmgm            306    313    313    309    313   312   313   313     402
     betrivers           3      3      3      3      3     3     3     3     402
     betus               0      0      5     10     10    10    10    10     402
     fanatics           59     58     58     58     59    58    58    58     402
     fanduel           310    314    314    314    314   313   313   313     402
2027 ANY BOOK          107    107    107    107    107   107   107   107     107
     ANY DECIDABLE     107    107    107    107    107   107   107   107     107
     betmgm              4      5      4      5      5     4     4     4     107
     betrivers          99    105    107    107    107   107   107   106     107
     fanduel           107    107    105    107    107   107   107   107     107
-- off-centre main quotes set aside (spreads_q1): rows, games, by season and book
                  rows  games
season bookmaker             
2026   betmgm       24      3
2027   betmgm      794    101

==== totals_q1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           36    211    269    291    303   310   313   317     331
     betus              36    211    269    291    303   310   313   317     331
2025 ANY BOOK           12     87    166    214    230   237   244   247     330
     betus              12     87    166    214    230   237   244   247     330
2026 ANY BOOK          274    278    283    284    283   283   283   324     402
     ANY DECIDABLE     274    278    278    274    273   273   273   314     402
     betmgm            217    224    224    219    222   221   222   222     402
     betus               0      0      5     10     10    10    10    10     402
     fanatics           59     58     58     58     59    58    58    58     402
     fanduel           274    278    278    274    273   272   272   313     402
2027 ANY BOOK           99    105    107    107    107   107   107   107     107
     ANY DECIDABLE      99    105    107    107    107   107   107   107     107
     betrivers          99    105    107    107    107   107   107   106     107
     fanduel             0      0      0      0      0     0     0   107     107
-- off-centre main quotes set aside (totals_q1): rows, games, by season and book
                  rows  games
season bookmaker             
2026   betmgm       24      3
2027   betmgm      829    104

==== h2h_q1: games with an on-centre main quote, by season, book and mark ====
mark                T-1440  T-720  T-360  T-180  T-120  T-60  T-30  T-10  played
2024 ANY BOOK           34     94    188    244    255   263   267   273     331
     betus              34     94    188    244    255   263   267   273     331
2025 ANY BOOK            4      2     33     65     77    85    89    89     330
     betus               4      2     33     65     77    85    89    89     330
2026 ANY BOOK          253    312    320    320    320   320   320   320     402
     ANY DECIDABLE     253    312    316    316    316   316   316   316     402
     betmgm              3      3      3      3      3     3     3     3     402
     betrivers         253    312    316    316    316   316   316   316     402
     betus               0      0      4      4      4     4     4     4     402
2027 ANY BOOK          105    106    107    107    107   107   107   107     107
     ANY DECIDABLE     105    106    107    107    107   107   107   107     107
     betmgm            103    103    103    104    104   104   104   104     107
     betrivers          99    105    107    107    107   107   107   106     107

==== stored snapshot time before tip, by mark (minutes; main markets) ====
          count    mean  std     min      5%     50%     95%     max
mark                                                                
T-1440   8250.0  1444.8  1.1  1443.5  1444.0  1444.8  1445.7  1481.3
T-720   10852.0   725.0  1.4   723.8   724.2   724.8   726.0   771.3
T-360   12028.0   364.9  0.6   363.8   364.2   364.8   366.0   372.1
T-180   12540.0   184.9  0.5   183.8   184.2   184.8   185.7   196.8
T-120   12697.0   124.9  0.6   123.8   124.2   124.8   125.7   135.9
T-60    12752.0    64.9  0.6    63.7    64.2    64.8    65.7    77.7
T-30    12790.0    34.9  1.1    33.7    34.2    34.8    35.7    72.6
T-10    12952.0    14.9  1.9    13.6    14.2    14.8    15.7    72.6
```

**Best price is often one book.** On the modal decidable number at T-10, a
real shop (2+ decidable books on the same number) existed on 176 of 316
first-half spread games in 2025-26 and 74 of 107 in 2026-27; 141 of 316 and 58
of 107 for first-half totals; the first-quarter moneyline in 2025-26 was
BetRivers alone on 313 of 316 games.

Printed by `scripts/euroleague_research/r1_nbooks.py`:

```
==== (1) decidable books on the modal decidable number at T-10 (games) ====
    market  season  games  one_book  two_books  three_plus
spreads_h1    2026    316       140        176           0
spreads_h1    2027    107        33         74           0
 totals_h1    2026    316       175        141           0
 totals_h1    2027    107        49         58           0
spreads_q1    2026    316       160        156           0
spreads_q1    2027    107        20         87           0
 totals_q1    2026    314       188        126           0
 totals_q1    2027    107        37         70           0
    h2h_h1    2026    358        43         29         286
    h2h_h1    2027    107         0          3         104
    h2h_q1    2026    316       313          3           0
    h2h_q1    2027    107         4        103           0

==== (2) on-centre main quotes: distance from the other books' median number, same (game, mark) ====
    market  season       book  quotes  share_ge1  share_ge2  median_abs
spreads_h1    2025      betus    1734      0.159      0.009      0.5000
spreads_h1    2025     gtbets    1734      0.159      0.009      0.5000
spreads_h1    2026     betmgm    2506      0.291      0.021      0.2500
spreads_h1    2026  betrivers      24      0.667      0.667      2.4975
spreads_h1    2026      betus    2381      0.083      0.000      0.0000
spreads_h1    2026   fanatics     339      0.788      0.614      2.0000
spreads_h1    2026    fanduel    2505      0.128      0.001      0.0000
spreads_h1    2026     gtbets    3075      0.058      0.000      0.0000
spreads_h1    2026 mybookieag     343      0.070      0.000      0.0000
spreads_h1    2027     betmgm     389      1.000      0.997      4.0000
spreads_h1    2027  betrivers     845      0.196      0.006      0.5000
spreads_h1    2027      betus     688      0.068      0.001      0.2500
spreads_h1    2027    fanduel     853      0.034      0.002      0.2500
spreads_h1    2027     gtbets     773      0.061      0.001      0.0000
spreads_h1    2027 mybookieag     697      0.009      0.000      0.0000
 totals_h1    2025      betus    1744      0.288      0.028      0.5000
 totals_h1    2025     gtbets    1744      0.288      0.028      0.5000
 totals_h1    2026     betmgm    2492      0.472      0.029      0.5000
 totals_h1    2026      betus    2389      0.205      0.014      0.5000
 totals_h1    2026   fanatics     355      0.828      0.642      2.0000
 totals_h1    2026    fanduel    2513      0.166      0.007      0.0000
 totals_h1    2026     gtbets    3079      0.245      0.015      0.5000
 totals_h1    2026 mybookieag     343      0.050      0.000      0.0000
 totals_h1    2027     betmgm     135      1.000      1.000      5.0000
 totals_h1    2027  betrivers     845      0.341      0.034      0.5000
 totals_h1    2027      betus     711      0.135      0.003      0.5000
 totals_h1    2027    fanduel     851      0.073      0.001      0.2500
 totals_h1    2027     gtbets     770      0.123      0.000      0.2500
 totals_h1    2027 mybookieag     697      0.019      0.000      0.2500
spreads_q1    2026     betmgm    2473      0.517      0.043      1.0000
spreads_q1    2026  betrivers      24      0.625      0.250      1.4985
spreads_q1    2026   fanatics     466      0.809      0.403      1.5000
spreads_q1    2026    fanduel    2500      0.478      0.016      0.5000
spreads_q1    2027     betmgm      35      1.000      1.000      3.0000
spreads_q1    2027  betrivers     843      0.227      0.024      0.0000
spreads_q1    2027    fanduel     843      0.211      0.000      0.0000
 totals_q1    2026     betmgm    1768      0.437      0.041      0.0000
 totals_q1    2026   fanatics     466      0.852      0.395      1.5000
 totals_q1    2026    fanduel    1772      0.378      0.002      0.0000
 totals_q1    2027  betrivers     106      0.340      0.000      0.0000
 totals_q1    2027    fanduel     106      0.340      0.000      0.0000
```

## 4. Baselines (task 2)

Every blind bet, per market, season and decision (T-10; each game's earliest
stored mark), at each book's own number and price and at the best decidable
price. 556 cells; 502 with 25+ bets; 103 of those positive; **0 survive
Benjamini-Hochberg at a 10% false-discovery rate, and no positive cell has a
90% interval above zero.**

The pooled table (2025-26 + 2026-27 at the best decidable price; offshore books
over every season, reference only) is the one to read first. Best and worst
pooled at the best decidable price, T-10:

| Market | Best blind side | Worst blind side |
|---|---|---|
| First-half spread | underdog: 423 bets, -8.59 units, -1.75% [-8.59, +4.70] | favourite: 423 bets, -50.67 units, -10.65% [-17.21, -3.55] |
| First-half total | over: 423, -27.86, -5.58% [-12.38, +1.25] | under: 423, -36.00, -7.54% [-14.60, -0.57] |
| First-half moneyline | underdog: 465, +19.14, +4.22% [-4.64, +12.35] | favourite: 465, -81.98, -9.67% [-14.56, -4.29] |
| First-quarter spread | home: 423, -8.00, -1.69% [-9.72, +6.10] | away: 423, -52.67, -10.54% [-18.08, -2.54] |
| First-quarter total | under: 421, -25.22, -5.36% [-11.88, +1.27] | over: 421, -33.63, -6.83% [-13.27, -0.54] |
| First-quarter moneyline | underdog: 421, -13.07, -3.21% [-12.66, +5.75] | away: 423, -50.43, -10.80% [-19.39, -2.00] |

One pattern repeats: **the first-half favourite loses more than the underdog**
on the spread at the offshore reference in every season (BetUS pooled:
favourite -13.33% on 1,082 bets, underdog -2.17%) and at the decidable books in
2025-26 (favourite -13.23%, underdog +0.78%), though 2026-27 to date reverses it
(favourite -2.99%, underdog -9.38% on 107). The underdog never clears zero
pooled. The only pooled positive, the first-half moneyline underdog, is taken
through the kill tests in section 7 (P4) and fails them.

Printed by `scripts/euroleague_research/r1_baselines.py`:

```
cells printed: 556; with 25+ bets: 502; positive with 25+ bets: 103; surviving Benjamini-Hochberg at FDR 10% (one-sided bootstrap p): 0
Empty DataFrame
Columns: [market, season, decision, book, side, bets, W, L, P, units, ret%, lo%, hi%, u/bet]
Index: []
positive cells with 25+ bets whose 90% interval is above zero:
Empty DataFrame
Columns: [market, season, decision, book, side, bets, W, L, P, units, ret%, lo%, hi%, u/bet]
Index: []

==== spreads_h1 ====
    market  season decision             book side  bets   W   L  P  units   ret%     lo%    hi%   u/bet
spreads_h1    2024     T-10      betus (ref) home   320 162 151  7 -18.71  -5.00  -12.97   2.53 -0.0585
spreads_h1    2024     T-10      betus (ref) away   320 151 162  7 -42.55 -11.39  -18.96  -3.35 -0.1330
spreads_h1    2024     T-10      betus (ref)  fav   315 149 159  7 -41.36 -11.22  -19.46  -3.67 -0.1313
spreads_h1    2024     T-10      betus (ref)  dog   315 159 149  7 -18.90  -5.14  -12.70   3.20 -0.0600
spreads_h1    2024 earliest      betus (ref) home   321 165 146 10  -9.61  -2.58  -11.16   5.02 -0.0299
spreads_h1    2024 earliest      betus (ref) away   321 146 165 10 -50.86 -13.71  -21.36  -5.16 -0.1584
spreads_h1    2024 earliest      betus (ref)  fav   321 156 155 10 -29.37  -7.90  -17.71   0.92 -0.0915
spreads_h1    2024 earliest      betus (ref)  dog   321 155 156 10 -31.10  -8.38  -17.25   1.44 -0.0969
spreads_h1    2025     T-10      betus (ref) home   299 154 139  6  -9.58  -2.78  -10.62   6.33 -0.0320
spreads_h1    2025     T-10      betus (ref) away   299 139 154  6 -42.29 -12.27  -21.43  -4.54 -0.1414
spreads_h1    2025     T-10      betus (ref)  fav   298 142 150  6 -34.79 -10.11  -19.41   0.03 -0.1167
spreads_h1    2025     T-10      betus (ref)  dog   298 150 142  6 -16.92  -4.93  -15.20   4.35 -0.0568
spreads_h1    2025     T-10     gtbets (ref) home   278 151 124  3   8.50   2.67   -5.92  11.41  0.0306
spreads_h1    2025     T-10     gtbets (ref) away   278 124 151  3 -48.00 -15.20  -23.96  -6.70 -0.1727
spreads_h1    2025     T-10     gtbets (ref)  fav   274 133 138  3 -22.97  -7.44  -17.24   2.60 -0.0838
spreads_h1    2025     T-10     gtbets (ref)  dog   274 138 133  3 -15.91  -5.03  -15.19   4.63 -0.0581
spreads_h1    2025 earliest      betus (ref) home   303 157 143  3 -11.75  -3.32  -11.57   5.96 -0.0388
spreads_h1    2025 earliest      betus (ref) away   303 143 157  3 -41.64 -11.82  -21.09  -3.46 -0.1374
spreads_h1    2025 earliest      betus (ref)  fav   302 152 147  3 -21.89  -6.19  -15.44   3.85 -0.0725
spreads_h1    2025 earliest      betus (ref)  dog   302 147 152  3 -31.35  -8.94  -19.05   0.29 -0.1038
spreads_h1    2025 earliest     gtbets (ref) home   283 155 127  1  10.13   3.12   -5.60  11.40  0.0358
spreads_h1    2025 earliest     gtbets (ref) away   283 127 155  1 -50.75 -15.59  -23.91  -7.06 -0.1793
spreads_h1    2025 earliest     gtbets (ref)  fav   281 140 140  1 -18.23  -5.71  -15.04   3.74 -0.0649
spreads_h1    2025 earliest     gtbets (ref)  dog   281 140 140  1 -22.04  -6.75  -16.02   2.33 -0.0784
spreads_h1    2026     T-10          fanduel home   313 152 161  0 -30.89  -8.69  -18.53   0.47 -0.0987
spreads_h1    2026     T-10          fanduel away   313 161 152  0 -10.24  -2.90  -12.15   7.16 -0.0327
spreads_h1    2026     T-10          fanduel  fav   313 144 169  0 -47.44 -13.38  -22.61  -5.28 -0.1516
spreads_h1    2026     T-10          fanduel  dog   313 169 144  0   6.31   1.79   -6.28  10.97  0.0202
spreads_h1    2026     T-10           betmgm home   314 155 159  0 -35.14  -9.27  -18.59  -0.40 -0.1119
spreads_h1    2026     T-10           betmgm away   314 159 155  0 -26.08  -6.93  -15.75   2.14 -0.0831
spreads_h1    2026     T-10           betmgm  fav   314 146 168  0 -50.25 -13.58  -22.25  -4.93 -0.1600
spreads_h1    2026     T-10           betmgm  dog   314 168 146  0 -10.97  -2.84  -11.08   5.37 -0.0349
spreads_h1    2026     T-10        betrivers home     3   2   1  0   1.00  29.67    0.00  89.29  0.3333
spreads_h1    2026     T-10        betrivers away     3   1   2  0  -1.34 -35.08 -100.00  -3.88 -0.4467
spreads_h1    2026     T-10        betrivers  fav     3   2   1  0   1.00  29.67    0.00  89.29  0.3333
spreads_h1    2026     T-10        betrivers  dog     3   1   2  0  -1.34 -35.08 -100.00  -3.88 -0.4467
spreads_h1    2026     T-10         fanatics home    26  11  15  0  -6.70 -16.92  -39.06   0.00 -0.2577
spreads_h1    2026     T-10         fanatics away    26  15  11  0   3.60   9.11   -7.42  28.06  0.1385
spreads_h1    2026     T-10         fanatics  fav    26  11  15  0  -3.55 -10.14  -36.85  16.78 -0.1365
spreads_h1    2026     T-10         fanatics  dog    26  15  11  0   0.45   1.02  -23.12  24.17  0.0173
spreads_h1    2026     T-10      betus (ref) home   366 169 194  3 -59.68 -13.93  -21.80  -5.78 -0.1631
spreads_h1    2026     T-10      betus (ref) away   366 194 169  3  -5.73  -1.34   -9.50   6.53 -0.0157
spreads_h1    2026     T-10      betus (ref)  fav   366 157 206  3 -86.14 -20.09  -27.76 -12.13 -0.2354
spreads_h1    2026     T-10      betus (ref)  dog   366 206 157  3  20.73   4.84   -3.22  12.57  0.0566
spreads_h1    2026     T-10     gtbets (ref) home   402 192 202  8 -40.52  -8.93  -16.91  -1.01 -0.1008
spreads_h1    2026     T-10     gtbets (ref) away   402 202 192  8 -18.66  -4.12  -12.22   3.95 -0.0464
spreads_h1    2026     T-10     gtbets (ref)  fav   386 169 209  8 -71.50 -16.43  -24.45  -9.32 -0.1852
spreads_h1    2026     T-10     gtbets (ref)  dog   386 209 169  8  14.65   3.37   -3.71  11.38  0.0380
spreads_h1    2026     T-10 mybookieag (ref) home    41  15  26  0 -15.93 -32.68  -61.30  -6.38 -0.3885
spreads_h1    2026     T-10 mybookieag (ref) away    41  26  15  0   8.55  17.93   -8.93  47.09  0.2085
spreads_h1    2026     T-10 mybookieag (ref)  fav    40  16  24  0 -12.07 -25.88  -51.32  -2.12 -0.3017
spreads_h1    2026     T-10 mybookieag (ref)  dog    40  24  16  0   4.89  10.31  -13.17  35.68  0.1223
spreads_h1    2026     T-10   BEST decidable home   316 152 164  0 -31.10  -8.79  -18.93   0.37 -0.0984
spreads_h1    2026     T-10   BEST decidable away   316 164 152  0 -13.08  -3.53  -12.30   6.49 -0.0414
spreads_h1    2026     T-10   BEST decidable  fav   316 145 171  0 -47.07 -13.23  -21.47  -5.39 -0.1490
spreads_h1    2026     T-10   BEST decidable  dog   316 171 145  0   2.89   0.78   -6.78   8.79  0.0091
spreads_h1    2026 earliest          fanduel home   314 152 162  0 -31.98  -8.98  -18.23  -0.35 -0.1018
spreads_h1    2026 earliest          fanduel away   314 162 152  0  -9.64  -2.72  -11.37   6.59 -0.0307
spreads_h1    2026 earliest          fanduel  fav   314 144 170  0 -48.13 -13.59  -22.30  -5.71 -0.1533
spreads_h1    2026 earliest          fanduel  dog   314 170 144  0   6.51   1.83   -6.05  10.54  0.0207
spreads_h1    2026 earliest           betmgm home   316 152 164  0 -43.28 -11.40  -20.84  -2.80 -0.1370
spreads_h1    2026 earliest           betmgm away   316 164 152  0 -18.49  -4.82  -13.35   4.30 -0.0585
spreads_h1    2026 earliest           betmgm  fav   316 145 171  0 -53.32 -14.43  -22.52  -6.77 -0.1687
spreads_h1    2026 earliest           betmgm  dog   316 171 145  0  -8.45  -2.15   -9.50   5.71 -0.0267
spreads_h1    2026 earliest        betrivers home     3   2   1  0   1.00  30.49   -0.00  88.50  0.3333
spreads_h1    2026 earliest        betrivers away     3   1   2  0  -1.44 -36.73 -100.00  -7.46 -0.4800
spreads_h1    2026 earliest        betrivers  fav     3   2   1  0   1.00  30.49   -0.00  88.50  0.3333
spreads_h1    2026 earliest        betrivers  dog     3   1   2  0  -1.44 -36.73 -100.00  -7.46 -0.4800
spreads_h1    2026 earliest         fanatics home    63  31  32  0  -6.20  -8.32  -29.20  11.86 -0.0984
spreads_h1    2026 earliest         fanatics away    63  32  31  0  -3.50  -4.76  -25.55  15.83 -0.0556
spreads_h1    2026 earliest         fanatics  fav    63  29  34  0 -10.10 -13.85  -34.57   7.93 -0.1603
spreads_h1    2026 earliest         fanatics  dog    63  34  29  0   0.40   0.53  -20.89  20.34  0.0063
spreads_h1    2026 earliest      betus (ref) home   369 176 189  4 -47.58 -11.05  -18.76  -2.68 -0.1289
spreads_h1    2026 earliest      betus (ref) away   369 189 176  4 -19.66  -4.56  -12.98   3.06 -0.0533
spreads_h1    2026 earliest      betus (ref)  fav   369 165 200  4 -71.68 -16.66  -24.05  -8.82 -0.1943
spreads_h1    2026 earliest      betus (ref)  dog   369 200 165  4   4.44   1.03   -6.84   8.47  0.0120
spreads_h1    2026 earliest     gtbets (ref) home   402 192 204  6 -42.43  -9.34  -17.08  -1.42 -0.1055
spreads_h1    2026 earliest     gtbets (ref) away   402 204 192  6 -17.72  -3.88  -11.77   3.91 -0.0441
spreads_h1    2026 earliest     gtbets (ref)  fav   391 174 211  6 -68.97 -15.57  -23.34  -7.42 -0.1764
spreads_h1    2026 earliest     gtbets (ref)  dog   391 211 174  6  10.51   2.37   -5.69  10.17  0.0269
spreads_h1    2026 earliest mybookieag (ref) home    80  35  45  0 -17.57 -18.67  -37.76   0.90 -0.2196
spreads_h1    2026 earliest mybookieag (ref) away    80  45  35  0   4.32   4.60  -15.33  23.61  0.0540
spreads_h1    2026 earliest mybookieag (ref)  fav    79  35  44  0 -16.15 -17.46  -34.97  -0.18 -0.2044
spreads_h1    2026 earliest mybookieag (ref)  dog    79  44  35  0   3.12   3.35  -14.15  21.17  0.0395
spreads_h1    2026 earliest   BEST decidable home   316 150 166  0 -36.40 -10.26  -20.00  -1.58 -0.1152
spreads_h1    2026 earliest   BEST decidable away   316 166 150  0  -6.88  -1.88  -10.38   7.59 -0.0218
spreads_h1    2026 earliest   BEST decidable  fav   316 142 174  0 -53.37 -15.06  -23.43  -7.42 -0.1689
spreads_h1    2026 earliest   BEST decidable  dog   316 174 142  0  10.09   2.75   -4.46  10.77  0.0319
spreads_h1    2027     T-10          fanduel home   107  59  48  0   4.80   3.97   -9.24  15.53  0.0449
spreads_h1    2027     T-10          fanduel away   107  48  59  0 -18.61 -15.39  -27.00  -2.25 -0.1739
spreads_h1    2027     T-10          fanduel  fav   107  54  53  0  -6.21  -5.10  -18.65   6.51 -0.0580
spreads_h1    2027     T-10          fanduel  dog   107  53  54  0  -7.60  -6.32  -18.38   7.17 -0.0710
spreads_h1    2027     T-10           betmgm home    47  20  27  0   1.92   4.09  -17.96  21.79  0.0409
spreads_h1    2027     T-10           betmgm away    47  27  20  0 -15.55 -15.59  -26.23  -2.32 -0.3309
spreads_h1    2027     T-10           betmgm  fav    47  20  27  0   1.92   4.09  -17.96  21.79  0.0409
spreads_h1    2027     T-10           betmgm  dog    47  27  20  0 -15.55 -15.59  -26.23  -2.32 -0.3309
spreads_h1    2027     T-10        betrivers home   106  59  47  0   3.23   2.55  -10.54  14.06  0.0305
spreads_h1    2027     T-10        betrivers away   106  47  59  0 -24.20 -18.90  -30.25  -6.26 -0.2283
spreads_h1    2027     T-10        betrivers  fav   106  55  51  0  -5.20  -4.14  -17.19   8.23 -0.0491
spreads_h1    2027     T-10        betrivers  dog   106  51  55  0 -15.77 -12.24  -24.35   0.85 -0.1488
spreads_h1    2027     T-10      betus (ref) home   103  57  46  0   2.59   2.14  -11.34  13.94  0.0251
spreads_h1    2027     T-10      betus (ref) away   103  46  57  0 -20.87 -17.31  -29.26  -3.67 -0.2026
spreads_h1    2027     T-10      betus (ref)  fav   103  53  50  0  -6.07  -5.01  -18.58   7.06 -0.0589
spreads_h1    2027     T-10      betus (ref)  dog   103  50  53  0 -12.21 -10.12  -22.14   3.54 -0.1185
spreads_h1    2027     T-10     gtbets (ref) home    97  54  43  0   4.10   3.65  -10.94  16.02  0.0423
spreads_h1    2027     T-10     gtbets (ref) away    97  43  54  0 -18.85 -16.99  -29.47  -2.18 -0.1943
spreads_h1    2027     T-10     gtbets (ref)  fav    97  50  47  0  -4.24  -3.79  -19.05   9.25 -0.0437
spreads_h1    2027     T-10     gtbets (ref)  dog    97  47  50  0 -10.51  -9.43  -22.44   6.00 -0.1084
spreads_h1    2027     T-10 mybookieag (ref) home   100  54  44  2   2.37   2.05  -12.07  14.76  0.0237
spreads_h1    2027     T-10 mybookieag (ref) away   100  44  54  2 -19.09 -16.63  -29.28  -2.52 -0.1909
spreads_h1    2027     T-10 mybookieag (ref)  fav    97  50  45  2  -2.49  -2.24  -15.61   9.36 -0.0257
spreads_h1    2027     T-10 mybookieag (ref)  dog    97  45  50  2 -13.67 -12.22  -23.84   1.01 -0.1409
spreads_h1    2027     T-10   BEST decidable home   107  59  48  0   5.40   4.53   -8.85  16.11  0.0505
spreads_h1    2027     T-10   BEST decidable away   107  48  59  0 -20.48 -16.61  -28.06  -3.74 -0.1914
spreads_h1    2027     T-10   BEST decidable  fav   107  55  52  0  -3.60  -2.99  -16.84   8.88 -0.0336
spreads_h1    2027     T-10   BEST decidable  dog   107  52  55  0 -11.48  -9.38  -21.81   4.86 -0.1073
spreads_h1    2027 earliest          fanduel home   107  58  49  0   3.38   2.82  -10.57  15.00  0.0316
spreads_h1    2027 earliest          fanduel away   107  49  58  0 -16.86 -13.81  -25.76  -0.67 -0.1576
spreads_h1    2027 earliest          fanduel  fav   107  58  49  0   2.67   2.20  -11.15  14.07  0.0250
spreads_h1    2027 earliest          fanduel  dog   107  49  58  0 -16.15 -13.39  -25.13   0.04 -0.1509
spreads_h1    2027 earliest           betmgm home    60  24  36  0  -0.77  -1.28  -19.25  16.25 -0.0128
spreads_h1    2027 earliest           betmgm away    60  36  24  0 -15.85 -12.06  -22.44  -1.52 -0.2642
spreads_h1    2027 earliest           betmgm  fav    60  24  36  0  -0.77  -1.28  -19.25  16.25 -0.0128
spreads_h1    2027 earliest           betmgm  dog    60  36  24  0 -15.85 -12.06  -22.44  -1.52 -0.2642
spreads_h1    2027 earliest        betrivers home   107  59  48  0   1.93   1.50  -11.32  13.05  0.0180
spreads_h1    2027 earliest        betrivers away   107  48  59  0 -22.48 -17.39  -29.18  -4.51 -0.2101
spreads_h1    2027 earliest        betrivers  fav   107  58  49  0  -0.26  -0.20  -13.49  10.95 -0.0024
spreads_h1    2027 earliest        betrivers  dog   107  49  58  0 -20.29 -15.74  -27.04  -2.86 -0.1896
spreads_h1    2027 earliest      betus (ref) home   103  54  45  4   0.64   0.55  -13.86  13.29  0.0062
spreads_h1    2027 earliest      betus (ref) away   103  45  54  4 -18.16 -15.65  -28.56  -1.13 -0.1763
spreads_h1    2027 earliest      betus (ref)  fav   103  53  46  4  -1.17  -1.01  -14.28  10.97 -0.0114
spreads_h1    2027 earliest      betus (ref)  dog   103  46  53  4 -16.35 -14.03  -26.02  -0.87 -0.1587
spreads_h1    2027 earliest     gtbets (ref) home    97  53  43  1   3.87   3.52  -10.38  15.26  0.0399
spreads_h1    2027 earliest     gtbets (ref) away    97  43  53  1 -18.12 -16.33  -28.14  -2.65 -0.1868
spreads_h1    2027 earliest     gtbets (ref)  fav    97  53  43  1   3.87   3.52  -10.63  15.11  0.0399
spreads_h1    2027 earliest     gtbets (ref)  dog    97  43  53  1 -18.12 -16.33  -27.76  -2.29 -0.1868
spreads_h1    2027 earliest mybookieag (ref) home   100  55  45  0   2.05   1.74  -11.42  13.85  0.0205
spreads_h1    2027 earliest mybookieag (ref) away   100  45  55  0 -19.55 -16.67  -28.93  -3.31 -0.1955
spreads_h1    2027 earliest mybookieag (ref)  fav    95  51  44  0  -0.89  -0.80  -14.31  10.79 -0.0094
spreads_h1    2027 earliest mybookieag (ref)  dog    95  44  51  0 -15.81 -14.21  -26.09  -0.52 -0.1664
spreads_h1    2027 earliest   BEST decidable home   107  58  49  0   5.42   4.61   -8.41  16.53  0.0507
spreads_h1    2027 earliest   BEST decidable away   107  49  58  0 -20.12 -15.71  -27.23  -3.48 -0.1880
spreads_h1    2027 earliest   BEST decidable  fav   107  57  50  0   2.26   1.89  -11.75  14.00  0.0211
spreads_h1    2027 earliest   BEST decidable  dog   107  50  57  0 -16.96 -13.48  -25.48  -0.23 -0.1585

==== totals_h1 ====
   market  season decision             book  side  bets   W   L  P  units   ret%    lo%    hi%   u/bet
totals_h1    2024     T-10      betus (ref)  over   321 157 153 11 -26.25  -7.08 -15.52   1.77 -0.0818
totals_h1    2024     T-10      betus (ref) under   321 153 157 11 -34.50  -9.32 -18.16  -0.90 -0.1075
totals_h1    2024 earliest      betus (ref)  over   321 158 158  5 -30.81  -8.17 -17.33   1.04 -0.0960
totals_h1    2024 earliest      betus (ref) under   321 158 158  5 -30.59  -8.10 -17.26   1.06 -0.0953
totals_h1    2025     T-10      betus (ref)  over   301 145 152  4 -32.90  -9.45 -17.32  -0.91 -0.1093
totals_h1    2025     T-10      betus (ref) under   301 152 145  4 -19.42  -5.52 -14.13   2.29 -0.0645
totals_h1    2025     T-10     gtbets (ref)  over   278 132 143  3 -33.55 -10.60 -20.14  -1.18 -0.1207
totals_h1    2025     T-10     gtbets (ref) under   278 143 132  3 -10.01  -3.16 -12.67   6.38 -0.0360
totals_h1    2025 earliest      betus (ref)  over   303 150 148  5 -23.89  -6.82 -15.08   1.89 -0.0788
totals_h1    2025 earliest      betus (ref) under   303 148 150  5 -28.52  -8.13 -16.86   0.14 -0.0941
totals_h1    2025 earliest     gtbets (ref)  over   283 138 142  3 -25.40  -7.88 -17.41   1.39 -0.0898
totals_h1    2025 earliest     gtbets (ref) under   283 142 138  3 -16.92  -5.24 -14.59   4.38 -0.0598
totals_h1    2026     T-10          fanduel  over   314 160 154  0 -13.50  -3.82 -11.86   4.67 -0.0430
totals_h1    2026     T-10          fanduel under   314 154 160  0 -27.38  -7.69 -16.17   0.43 -0.0872
totals_h1    2026     T-10           betmgm  over   313 158 155  0 -29.54  -7.78 -16.03   0.22 -0.0944
totals_h1    2026     T-10           betmgm under   313 155 158  0 -33.57  -8.94 -17.19  -0.48 -0.1073
totals_h1    2026     T-10         fanatics  over    29  15  14  0  -4.35  -9.14 -35.28  17.97 -0.1500
totals_h1    2026     T-10         fanatics under    29  14  15  0  -1.20  -3.03 -33.38  27.34 -0.0414
totals_h1    2026     T-10      betus (ref)  over   368 193 171  4  -8.93  -2.08  -9.97   5.91 -0.0243
totals_h1    2026     T-10      betus (ref) under   368 171 193  4 -56.93 -13.24 -21.19  -5.23 -0.1547
totals_h1    2026     T-10     gtbets (ref)  over   402 203 198  1 -24.22  -5.27 -12.65   2.18 -0.0602
totals_h1    2026     T-10     gtbets (ref) under   402 198 203  1 -36.36  -7.86 -15.32  -0.47 -0.0904
totals_h1    2026     T-10 mybookieag (ref)  over    41  26  15  0   8.43  17.53  -9.09  46.07  0.2056
totals_h1    2026     T-10 mybookieag (ref) under    41  15  26  0 -15.55 -32.28 -60.85  -5.59 -0.3793
totals_h1    2026     T-10   BEST decidable  over   316 162 154  0 -21.28  -5.65 -13.20   2.19 -0.0673
totals_h1    2026     T-10   BEST decidable under   316 154 162  0 -28.58  -8.01 -16.13  -0.37 -0.0904
totals_h1    2026 earliest          fanduel  over   315 165 150  0  -3.49  -0.99  -8.60   7.28 -0.0111
totals_h1    2026 earliest          fanduel under   315 150 165  0 -38.27 -10.66 -18.75  -3.16 -0.1215
totals_h1    2026 earliest           betmgm  over   313 161 152  0 -24.36  -6.39 -14.69   1.62 -0.0778
totals_h1    2026 earliest           betmgm under   313 152 161  0 -39.72 -10.66 -18.84  -2.03 -0.1269
totals_h1    2026 earliest         fanatics  over    63  30  33  0  -8.50 -11.60 -25.67   1.63 -0.1349
totals_h1    2026 earliest         fanatics under    63  33  30  0  -1.80  -2.44 -15.43  11.87 -0.0286
totals_h1    2026 earliest      betus (ref)  over   370 193 171  6  -9.20  -2.14  -9.84   5.91 -0.0249
totals_h1    2026 earliest      betus (ref) under   370 171 193  6 -57.01 -13.26 -21.39  -5.44 -0.1541
totals_h1    2026 earliest     gtbets (ref)  over   402 203 197  2 -22.77  -4.97 -12.65   2.60 -0.0566
totals_h1    2026 earliest     gtbets (ref) under   402 197 203  2 -37.41  -8.10 -15.74  -0.46 -0.0931
totals_h1    2026 earliest mybookieag (ref)  over    80  49  31  0  12.67  13.52  -4.15  30.11  0.1584
totals_h1    2026 earliest mybookieag (ref) under    80  31  49  0 -26.69 -28.35 -45.24 -10.69 -0.3336
totals_h1    2026 earliest   BEST decidable  over   316 165 151  0 -12.41  -3.35 -10.83   4.80 -0.0393
totals_h1    2026 earliest   BEST decidable under   316 151 165  0 -35.65  -9.99 -18.06  -2.39 -0.1128
totals_h1    2027     T-10          fanduel  over   107  52  55  0 -10.00  -8.26 -21.20   4.42 -0.0935
totals_h1    2027     T-10          fanduel under   107  55  52  0  -3.46  -2.87 -15.54  10.00 -0.0323
totals_h1    2027     T-10           betmgm  over    22   7  15  0  -4.50 -20.45 -53.64  19.53 -0.2045
totals_h1    2027     T-10           betmgm under    22  15   7  0  -0.45  -0.94 -24.49  18.38 -0.0205
totals_h1    2027     T-10        betrivers  over   106  53  53  0  -9.98  -7.85 -19.41   2.45 -0.0942
totals_h1    2027     T-10        betrivers under   106  53  53  0  -9.78  -7.70 -17.80   4.05 -0.0923
totals_h1    2027     T-10      betus (ref)  over   106  51  55  0 -13.42 -10.84 -23.26   1.42 -0.1266
totals_h1    2027     T-10      betus (ref) under   106  55  51  0  -5.46  -4.37 -16.83   7.87 -0.0515
totals_h1    2027     T-10     gtbets (ref)  over    96  46  49  1 -10.30  -9.41 -22.36   2.74 -0.1073
totals_h1    2027     T-10     gtbets (ref) under    96  49  46  1  -3.66  -3.35 -15.37   9.58 -0.0381
totals_h1    2027     T-10 mybookieag (ref)  over   100  49  51  0 -10.73  -9.17 -22.97   3.61 -0.1073
totals_h1    2027     T-10 mybookieag (ref) under   100  51  49  0  -6.77  -5.75 -18.79   7.77 -0.0677
totals_h1    2027     T-10   BEST decidable  over   107  54  53  0  -6.58  -5.34 -17.86   6.23 -0.0615
totals_h1    2027     T-10   BEST decidable under   107  53  54  0  -7.42  -6.16 -17.94   6.15 -0.0693
totals_h1    2027 earliest          fanduel  over   107  51  56  0 -12.23 -10.16 -22.06   1.47 -0.1143
totals_h1    2027 earliest          fanduel under   107  56  51  0  -2.04  -1.68 -13.36  10.35 -0.0191
totals_h1    2027 earliest           betmgm  over    26   9  17  0  -3.08 -11.85 -42.02  27.50 -0.1185
totals_h1    2027 earliest           betmgm under    26  17   9  0  -3.40  -5.76 -27.98  11.40 -0.1308
totals_h1    2027 earliest        betrivers  over   107  53  54  0 -12.34  -9.53 -21.40   0.67 -0.1153
totals_h1    2027 earliest        betrivers under   107  54  53  0  -9.63  -7.52 -18.40   4.44 -0.0900
totals_h1    2027 earliest      betus (ref)  over   106  52  52  2  -8.89  -7.28 -19.62   4.54 -0.0839
totals_h1    2027 earliest      betus (ref) under   106  52  52  2  -9.74  -7.89 -19.85   4.47 -0.0919
totals_h1    2027 earliest     gtbets (ref)  over    97  48  48  1  -6.90  -6.28 -19.67   4.71 -0.0711
totals_h1    2027 earliest     gtbets (ref) under    97  48  48  1  -7.51  -6.76 -17.69   6.53 -0.0774
totals_h1    2027 earliest mybookieag (ref)  over   100  48  50  2 -10.49  -9.14 -22.33   2.40 -0.1049
totals_h1    2027 earliest mybookieag (ref) under   100  50  48  2  -6.46  -5.60 -17.18   7.49 -0.0646
totals_h1    2027 earliest   BEST decidable  over   107  53  54  0 -10.50  -8.39 -20.44   2.25 -0.0981
totals_h1    2027 earliest   BEST decidable under   107  54  53  0  -5.81  -4.82 -15.51   7.38 -0.0543

==== h2h_h1 ====
market  season decision             book side  bets   W   L  P  units   ret%    lo%    hi%   u/bet
h2h_h1    2024     T-10      betus (ref) home   265 157  97 11   0.74   0.16  -6.89   7.72  0.0028
h2h_h1    2024     T-10      betus (ref) away   265  97 157 11 -47.96 -15.99 -26.90  -5.75 -0.1810
h2h_h1    2024     T-10      betus (ref)  fav   256 162  85  9  -1.23  -0.25  -7.52   6.38 -0.0048
h2h_h1    2024     T-10      betus (ref)  dog   256  85 162  9 -44.59 -17.76 -29.06  -5.17 -0.1742
h2h_h1    2024 earliest      betus (ref) home   279 166 102 11   7.59   1.62  -5.41   8.96  0.0272
h2h_h1    2024 earliest      betus (ref) away   279 102 166 11 -55.75 -17.58 -28.05  -7.60 -0.1998
h2h_h1    2024 earliest      betus (ref)  fav   265 168  87 10   4.83   0.98  -6.44   8.14  0.0182
h2h_h1    2024 earliest      betus (ref)  dog   265  87 168 10 -50.39 -19.36 -30.95  -7.16 -0.1902
h2h_h1    2025     T-10      betus (ref) home   195 108  80  7 -24.92  -7.14 -15.77   1.02 -0.1278
h2h_h1    2025     T-10      betus (ref) away   195  80 108  7 -15.67  -6.66 -17.62   5.13 -0.0804
h2h_h1    2025     T-10      betus (ref)  fav   194 118  69  7 -24.42  -6.22 -15.12   2.71 -0.1259
h2h_h1    2025     T-10      betus (ref)  dog   194  69 118  7 -15.98  -8.43 -23.71   7.04 -0.0824
h2h_h1    2025     T-10     gtbets (ref) home   285 163 112 10 -14.15  -2.93 -10.55   4.03 -0.0497
h2h_h1    2025     T-10     gtbets (ref) away   285 112 163 10 -40.09 -12.11 -21.52  -1.86 -0.1407
h2h_h1    2025     T-10     gtbets (ref)  fav   282 161 111 10 -42.17  -7.93 -15.27  -0.41 -0.1495
h2h_h1    2025     T-10     gtbets (ref)  dog   282 111 161 10 -11.62  -4.22 -16.47   7.76 -0.0412
h2h_h1    2025 earliest      betus (ref) home   203 113  83  7 -24.99  -6.86 -14.82   1.79 -0.1231
h2h_h1    2025 earliest      betus (ref) away   203  83 113  7 -16.37  -6.74 -18.49   3.64 -0.0806
h2h_h1    2025 earliest      betus (ref)  fav   200 122  71  7 -24.40  -6.03 -13.43   2.06 -0.1220
h2h_h1    2025 earliest      betus (ref)  dog   200  71 122  7 -16.36  -8.39 -22.28   4.53 -0.0818
h2h_h1    2025 earliest     gtbets (ref) home   285 163 112 10 -14.23  -2.95 -10.55   4.10 -0.0499
h2h_h1    2025 earliest     gtbets (ref) away   285 112 163 10 -39.31 -11.98 -21.30  -1.70 -0.1379
h2h_h1    2025 earliest     gtbets (ref)  fav   280 161 110  9 -39.44  -7.48 -14.09  -0.48 -0.1409
h2h_h1    2025 earliest     gtbets (ref)  dog   280 110 161  9 -13.50  -4.93 -16.30   5.79 -0.0482
h2h_h1    2026     T-10          fanduel home   287 156 121 10 -32.86  -6.65 -13.45   0.52 -0.1145
h2h_h1    2026     T-10          fanduel away   287 121 156 10 -20.77  -6.31 -16.58   3.63 -0.0724
h2h_h1    2026     T-10          fanduel  fav   284 156 118 10 -62.00 -11.48 -17.70  -5.19 -0.2183
h2h_h1    2026     T-10          fanduel  dog   284 118 156 10   8.76   3.17  -7.51  13.65  0.0308
h2h_h1    2026     T-10           betmgm home   356 195 150 11 -44.30  -7.28 -13.80  -1.12 -0.1244
h2h_h1    2026     T-10           betmgm away   356 150 195 11 -46.64 -11.28 -19.20  -2.47 -0.1310
h2h_h1    2026     T-10           betmgm  fav   354 194 149 11 -82.42 -12.30 -18.56  -6.61 -0.2328
h2h_h1    2026     T-10           betmgm  dog   354 149 194 11  -8.12  -2.34 -11.11   7.14 -0.0229
h2h_h1    2026     T-10        betrivers home   316 173 133 10 -48.43  -8.47 -15.89  -1.50 -0.1533
h2h_h1    2026     T-10        betrivers away   316 133 173 10 -22.47  -6.01 -15.98   4.63 -0.0711
h2h_h1    2026     T-10        betrivers  fav   315 172 133 10 -96.13 -15.12 -21.74  -8.89 -0.3052
h2h_h1    2026     T-10        betrivers  dog   315 133 172 10  25.36   8.25  -2.86  19.87  0.0805
h2h_h1    2026     T-10      betus (ref) home   218 124  88  6 -38.34  -8.92 -18.23  -0.62 -0.1759
h2h_h1    2026     T-10      betus (ref) away   218  88 124  6 -12.76  -5.13 -17.70   8.89 -0.0585
h2h_h1    2026     T-10      betus (ref)  fav   217 129  82  6 -49.17 -10.59 -18.73  -3.26 -0.2266
h2h_h1    2026     T-10      betus (ref)  dog   217  82 129  6  -1.73  -0.82 -14.02  13.63 -0.0080
h2h_h1    2026     T-10     gtbets (ref) home   402 221 169 12 -45.66  -6.64 -12.52  -0.43 -0.1136
h2h_h1    2026     T-10     gtbets (ref) away   402 169 221 12 -38.93  -8.45 -16.88  -0.48 -0.0968
h2h_h1    2026     T-10     gtbets (ref)  fav   395 215 168 12 -93.95 -12.61 -18.72  -7.35 -0.2379
h2h_h1    2026     T-10     gtbets (ref)  dog   395 168 215 12  10.41   2.69  -5.85  12.51  0.0264
h2h_h1    2026     T-10 mybookieag (ref) home    41  19  18  4 -10.21 -15.48 -34.78   4.03 -0.2491
h2h_h1    2026     T-10 mybookieag (ref) away    41  18  19  4   1.52   3.61 -21.87  29.07  0.0371
h2h_h1    2026     T-10 mybookieag (ref)  fav    40  20  16  4  -8.00 -11.65 -31.18   5.34 -0.2001
h2h_h1    2026     T-10 mybookieag (ref)  dog    40  16  20  4  -0.51  -1.38 -29.00  28.28 -0.0127
h2h_h1    2026     T-10   BEST decidable home   358 196 151 11 -30.05  -5.01 -11.92   1.31 -0.0839
h2h_h1    2026     T-10   BEST decidable away   358 151 196 11 -18.76  -4.61 -13.29   4.63 -0.0524
h2h_h1    2026     T-10   BEST decidable  fav   358 194 153 11 -78.08 -11.88 -18.46  -5.70 -0.2181
h2h_h1    2026     T-10   BEST decidable  dog   358 153 194 11  29.27   8.38  -1.85  19.57  0.0818
h2h_h1    2026 earliest          fanduel home   292 159 123 10 -33.64  -6.69 -13.58  -0.07 -0.1152
h2h_h1    2026 earliest          fanduel away   292 123 159 10 -21.63  -6.49 -15.84   3.45 -0.0741
h2h_h1    2026 earliest          fanduel  fav   290 155 125 10 -71.80 -13.07 -19.43  -6.94 -0.2476
h2h_h1    2026 earliest          fanduel  dog   290 125 155 10  16.78   5.94  -4.54  16.59  0.0579
h2h_h1    2026 earliest           betmgm home   358 196 151 11 -46.05  -7.50 -13.92  -1.26 -0.1286
h2h_h1    2026 earliest           betmgm away   358 151 196 11 -45.66 -11.10 -19.21  -2.63 -0.1275
h2h_h1    2026 earliest           betmgm  fav   355 193 151 11 -83.68 -12.49 -18.88  -6.42 -0.2357
h2h_h1    2026 earliest           betmgm  dog   355 151 193 11  -7.43  -2.13 -11.45   7.51 -0.0209
h2h_h1    2026 earliest        betrivers home   316 173 133 10 -47.41  -8.34 -15.53  -1.36 -0.1500
h2h_h1    2026 earliest        betrivers away   316 133 173 10 -23.18  -6.25 -16.18   4.29 -0.0734
h2h_h1    2026 earliest        betrivers  fav   313 168 135 10 -98.89 -15.77 -22.52  -9.53 -0.3159
h2h_h1    2026 earliest        betrivers  dog   313 135 168 10  28.72   9.41  -1.60  21.09  0.0918
h2h_h1    2026 earliest      betus (ref) home   235 131  96  8 -43.33  -9.55 -17.98  -1.78 -0.1844
h2h_h1    2026 earliest      betus (ref) away   235  96 131  8 -10.77  -4.08 -16.23   8.97 -0.0458
h2h_h1    2026 earliest      betus (ref)  fav   232 136  88  8 -49.91 -10.29 -18.39  -2.78 -0.2151
h2h_h1    2026 earliest      betus (ref)  dog   232  88 136  8  -3.60  -1.60 -14.89  12.76 -0.0155
h2h_h1    2026 earliest     gtbets (ref) home   402 221 169 12 -43.40  -6.35 -12.33  -0.12 -0.1080
h2h_h1    2026 earliest     gtbets (ref) away   402 169 221 12 -40.93  -8.94 -17.32  -0.95 -0.1018
h2h_h1    2026 earliest     gtbets (ref)  fav   390 212 166 12 -90.89 -12.41 -18.56  -7.18 -0.2330
h2h_h1    2026 earliest     gtbets (ref)  dog   390 166 212 12   8.36   2.19  -6.23  11.88  0.0214
h2h_h1    2026 earliest mybookieag (ref) home    80  39  37  4 -20.95 -15.41 -29.84  -0.31 -0.2619
h2h_h1    2026 earliest mybookieag (ref) away    80  37  39  4   1.73   1.96 -18.03  20.99  0.0216
h2h_h1    2026 earliest mybookieag (ref)  fav    80  40  36  4 -23.82 -16.28 -30.17  -3.10 -0.2977
h2h_h1    2026 earliest mybookieag (ref)  dog    80  36  40  4   4.59   5.88 -14.93  26.49  0.0574
h2h_h1    2026 earliest   BEST decidable home   358 196 151 11 -30.90  -5.14 -11.95   1.16 -0.0863
h2h_h1    2026 earliest   BEST decidable away   358 151 196 11 -20.94  -5.18 -13.85   4.02 -0.0585
h2h_h1    2026 earliest   BEST decidable  fav   356 191 154 11 -78.84 -12.07 -18.41  -6.16 -0.2215
h2h_h1    2026 earliest   BEST decidable  dog   356 154 191 11  27.33   7.87  -2.26  18.49  0.0768
h2h_h1    2027     T-10          fanduel home   107  64  39  4   2.85   1.59 -10.67  13.26  0.0266
h2h_h1    2027     T-10          fanduel away   107  39  64  4 -20.76 -16.96 -32.29  -0.60 -0.1940
h2h_h1    2027     T-10          fanduel  fav   106  63  39  4  -8.72  -4.44 -12.40   3.60 -0.0823
h2h_h1    2027     T-10          fanduel  dog   106  39  63  4  -9.06  -8.81 -21.91   4.38 -0.0855
h2h_h1    2027     T-10           betmgm home   105  63  38  4   3.79   2.16  -9.64  13.52  0.0361
h2h_h1    2027     T-10           betmgm away   105  38  63  4 -26.90 -21.90 -36.23  -6.73 -0.2562
h2h_h1    2027     T-10           betmgm  fav   104  63  37  4  -6.02  -3.09 -10.95   5.17 -0.0579
h2h_h1    2027     T-10           betmgm  dog   104  37  63  4 -16.89 -16.70 -29.75  -4.35 -0.1624
h2h_h1    2027     T-10        betrivers home   106  63  39  4   2.03   1.15 -10.67  12.77  0.0192
h2h_h1    2027     T-10        betrivers away   106  39  63  4 -26.11 -20.87 -35.43  -5.61 -0.2463
h2h_h1    2027     T-10        betrivers  fav   105  62  39  4  -9.94  -5.06 -12.66   2.87 -0.0946
h2h_h1    2027     T-10        betrivers  dog   105  39  62  4 -13.94 -13.53 -25.77  -1.48 -0.1328
h2h_h1    2027     T-10      betus (ref) home    81  47  32  2  -3.62  -2.56 -18.22  12.95 -0.0447
h2h_h1    2027     T-10      betus (ref) away    81  32  47  2 -12.50 -13.09 -34.33   7.60 -0.1543
h2h_h1    2027     T-10      betus (ref)  fav    80  50  28  2  -4.99  -3.21 -13.26   6.56 -0.0623
h2h_h1    2027     T-10      betus (ref)  dog    80  28  50  2 -10.94 -13.78 -29.02   1.89 -0.1367
h2h_h1    2027     T-10     gtbets (ref) home    97  58  35  4   1.50   0.90 -13.03  14.54  0.0155
h2h_h1    2027     T-10     gtbets (ref) away    97  35  58  4 -20.00 -17.98 -35.70   0.68 -0.2062
h2h_h1    2027     T-10     gtbets (ref)  fav    96  59  33  4  -5.33  -2.93 -11.42   5.44 -0.0555
h2h_h1    2027     T-10     gtbets (ref)  dog    96  33  59  4 -13.02 -14.00 -27.61  -0.57 -0.1356
h2h_h1    2027     T-10 mybookieag (ref) home   100  60  36  4   6.07   3.75  -9.41  17.00  0.0607
h2h_h1    2027     T-10 mybookieag (ref) away   100  36  60  4 -19.30 -17.43 -34.73   0.87 -0.1930
h2h_h1    2027     T-10 mybookieag (ref)  fav   100  61  35  4  -0.44  -0.25  -8.55   8.01 -0.0044
h2h_h1    2027     T-10 mybookieag (ref)  dog   100  35  61  4 -12.79 -13.24 -25.98  -0.07 -0.1279
h2h_h1    2027     T-10   BEST decidable home   107  64  39  4   6.25   3.61  -8.53  15.25  0.0584
h2h_h1    2027     T-10   BEST decidable away   107  39  64  4 -20.29 -16.73 -32.20  -0.11 -0.1896
h2h_h1    2027     T-10   BEST decidable  fav   107  64  39  4  -3.91  -2.05  -9.85   6.08 -0.0365
h2h_h1    2027     T-10   BEST decidable  dog   107  39  64  4 -10.13  -9.76 -22.81   3.24 -0.0947
h2h_h1    2027 earliest          fanduel home   107  64  39  4   2.11   1.17 -10.88  12.65  0.0197
h2h_h1    2027 earliest          fanduel away   107  39  64  4 -19.45 -15.88 -31.90   0.82 -0.1818
h2h_h1    2027 earliest          fanduel  fav   106  68  34  4   2.01   1.01  -6.51   8.63  0.0189
h2h_h1    2027 earliest          fanduel  dog   106  34  68  4 -19.22 -18.70 -31.35  -6.17 -0.1813
h2h_h1    2027 earliest           betmgm home   105  63  38  4   2.26   1.28 -10.31  12.76  0.0215
h2h_h1    2027 earliest           betmgm away   105  38  63  4 -24.86 -20.44 -35.15  -5.01 -0.2368
h2h_h1    2027 earliest           betmgm  fav   104  66  34  4   0.52   0.27  -8.18   8.85  0.0050
h2h_h1    2027 earliest           betmgm  dog   104  34  66  4 -22.92 -22.70 -35.63  -9.59 -0.2204
h2h_h1    2027 earliest        betrivers home   107  64  39  4   1.64   0.91 -11.14  12.18  0.0153
h2h_h1    2027 earliest        betrivers away   107  39  64  4 -25.63 -20.40 -35.22  -5.22 -0.2396
h2h_h1    2027 earliest        betrivers  fav   107  69  34  4   2.38   1.19  -6.20   8.69  0.0222
h2h_h1    2027 earliest        betrivers  dog   107  34  69  4 -26.37 -25.08 -36.56 -13.90 -0.2464
h2h_h1    2027 earliest      betus (ref) home    89  52  34  3  -1.82  -1.19 -14.25  11.47 -0.0205
h2h_h1    2027 earliest      betus (ref) away    89  34  52  3 -15.69 -15.12 -32.68   2.94 -0.1763
h2h_h1    2027 earliest      betus (ref)  fav    88  53  32  3  -7.91  -4.71 -13.01   4.19 -0.0899
h2h_h1    2027 earliest      betus (ref)  dog    88  32  53  3  -9.40 -10.85 -24.43   2.83 -0.1068
h2h_h1    2027 earliest     gtbets (ref) home    97  58  35  4   1.98   1.21 -12.20  14.23  0.0205
h2h_h1    2027 earliest     gtbets (ref) away    97  35  58  4 -19.48 -17.54 -35.37   1.04 -0.2008
h2h_h1    2027 earliest     gtbets (ref)  fav    96  61  31  4   0.58   0.32  -9.28  10.12  0.0060
h2h_h1    2027 earliest     gtbets (ref)  dog    96  31  61  4 -17.92 -19.28 -35.06  -3.25 -0.1867
h2h_h1    2027 earliest mybookieag (ref) home   100  60  36  4   5.28   3.22 -10.11  16.01  0.0528
h2h_h1    2027 earliest mybookieag (ref) away   100  36  60  4 -18.35 -16.58 -34.05   1.89 -0.1835
h2h_h1    2027 earliest mybookieag (ref)  fav   100  65  31  4   7.90   4.44  -3.74  12.50  0.0790
h2h_h1    2027 earliest mybookieag (ref)  dog   100  31  65  4 -20.97 -21.72 -34.23  -8.76 -0.2097
h2h_h1    2027 earliest   BEST decidable home   107  64  39  4   5.23   2.99  -8.90  14.41  0.0489
h2h_h1    2027 earliest   BEST decidable away   107  39  64  4 -19.00 -15.76 -31.71   1.04 -0.1776
h2h_h1    2027 earliest   BEST decidable  fav   107  67  36  4   2.28   1.19  -7.17   9.56  0.0213
h2h_h1    2027 earliest   BEST decidable  dog   107  36  67  4 -16.05 -15.46 -29.16  -0.97 -0.1500

==== spreads_q1 ====
    market  season decision           book side  bets   W   L  P  units   ret%     lo%    hi%   u/bet
spreads_q1    2024     T-10    betus (ref) home   316 150 166  0 -47.53 -12.64  -20.32  -4.60 -0.1504
spreads_q1    2024     T-10    betus (ref) away   316 166 150  0 -13.13  -3.48  -11.51   4.18 -0.0416
spreads_q1    2024     T-10    betus (ref)  fav   314 144 170  0 -58.22 -15.59  -24.12  -6.62 -0.1854
spreads_q1    2024     T-10    betus (ref)  dog   314 170 144  0  -2.04  -0.54   -9.45   7.96 -0.0065
spreads_q1    2024 earliest    betus (ref) home   316 152 164  0 -43.25 -11.48  -19.23  -2.82 -0.1369
spreads_q1    2024 earliest    betus (ref) away   316 164 152  0 -16.88  -4.49  -13.06   3.23 -0.0534
spreads_q1    2024 earliest    betus (ref)  fav   315 150 165  0 -46.31 -12.34  -20.46  -4.31 -0.1470
spreads_q1    2024 earliest    betus (ref)  dog   315 165 150  0 -13.62  -3.63  -11.71   4.45 -0.0432
spreads_q1    2025     T-10    betus (ref) home   245 137 108  0   8.40   2.85   -6.30  11.65  0.0343
spreads_q1    2025     T-10    betus (ref) away   245 108 137  0 -54.50 -18.62  -27.38  -9.52 -0.2224
spreads_q1    2025     T-10    betus (ref)  fav   245 124 121  0 -20.85  -7.05  -15.23   1.64 -0.0851
spreads_q1    2025     T-10    betus (ref)  dog   245 121 124  0 -25.25  -8.67  -17.39  -0.44 -0.1031
spreads_q1    2025 earliest    betus (ref) home   252 141 111  0   7.70   2.53   -6.25  11.59  0.0306
spreads_q1    2025 earliest    betus (ref) away   252 111 141  0 -56.45 -18.79  -27.97  -9.91 -0.2240
spreads_q1    2025 earliest    betus (ref)  fav   252 124 128  0 -30.25  -9.91  -18.21  -0.86 -0.1200
spreads_q1    2025 earliest    betus (ref)  dog   252 128 124  0 -18.50  -6.18  -15.20   2.20 -0.0734
spreads_q1    2026     T-10        fanduel home   313 159 154  0 -14.65  -4.13  -13.31   4.35 -0.0468
spreads_q1    2026     T-10        fanduel away   313 154 159  0 -25.46  -7.18  -15.76   2.10 -0.0813
spreads_q1    2026     T-10        fanduel  fav   313 149 164  0 -34.38  -9.79  -17.99  -1.00 -0.1098
spreads_q1    2026     T-10        fanduel  dog   313 164 149  0  -5.73  -1.60  -10.43   6.66 -0.0183
spreads_q1    2026     T-10         betmgm home   313 158 155  0 -28.07  -7.36  -16.67   0.80 -0.0897
spreads_q1    2026     T-10         betmgm away   313 155 158  0 -33.88  -8.88  -16.92   0.43 -0.1082
spreads_q1    2026     T-10         betmgm  fav   313 141 172  0 -51.30 -14.45  -24.22  -5.76 -0.1639
spreads_q1    2026     T-10         betmgm  dog   313 172 141  0 -10.65  -2.61  -10.70   6.41 -0.0340
spreads_q1    2026     T-10      betrivers home     3   2   1  0   0.90  23.14 -100.00  71.68  0.3000
spreads_q1    2026     T-10      betrivers away     3   1   2  0  -1.20 -34.58 -100.00  78.74 -0.4000
spreads_q1    2026     T-10      betrivers  fav     3   1   2  0  -1.10 -33.64 -100.00   0.00 -0.3667
spreads_q1    2026     T-10      betrivers  dog     3   2   1  0   0.80  19.56   -7.09  78.74  0.2667
spreads_q1    2026     T-10       fanatics home    58  28  30  0  -7.70  -9.05  -32.26  15.93 -0.1328
spreads_q1    2026     T-10       fanatics away    58  30  28  0  -1.10  -1.32  -25.48  21.15 -0.0190
spreads_q1    2026     T-10       fanatics  fav    58  19  39  0 -14.85 -23.89  -36.02 -12.29 -0.2560
spreads_q1    2026     T-10       fanatics  dog    58  39  19  0   6.05   5.71   -3.49  13.75  0.1043
spreads_q1    2026     T-10    betus (ref) home    10   5   5  0  -1.10  -9.05  -63.93  46.28 -0.1100
spreads_q1    2026     T-10    betus (ref) away    10   5   5  0  -0.85  -7.23  -62.39  47.46 -0.0850
spreads_q1    2026     T-10    betus (ref)  fav    10   5   5  0  -1.10  -9.05  -27.87   9.92 -0.1100
spreads_q1    2026     T-10    betus (ref)  dog    10   5   5  0  -0.85  -7.23  -24.79  10.17 -0.0850
spreads_q1    2026     T-10 BEST decidable home   316 156 160  0 -21.26  -6.01  -15.24   2.96 -0.0673
spreads_q1    2026     T-10 BEST decidable away   316 160 156  0 -24.39  -6.45  -15.05   2.59 -0.0772
spreads_q1    2026     T-10 BEST decidable  fav   316 146 170  0 -39.99 -11.49  -19.25  -3.24 -0.1266
spreads_q1    2026     T-10 BEST decidable  dog   316 170 146  0  -5.66  -1.48   -9.44   6.14 -0.0179
spreads_q1    2026 earliest        fanduel home   314 156 158  0 -20.36  -5.75  -14.93   2.93 -0.0648
spreads_q1    2026 earliest        fanduel away   314 158 156  0 -17.53  -4.91  -13.69   4.25 -0.0558
spreads_q1    2026 earliest        fanduel  fav   314 150 164  0 -30.90  -8.84  -17.47   0.09 -0.0984
spreads_q1    2026 earliest        fanduel  dog   314 164 150  0  -6.99  -1.93  -10.64   6.63 -0.0223
spreads_q1    2026 earliest         betmgm home   313 156 157  0 -29.60  -7.82  -17.07   0.38 -0.0946
spreads_q1    2026 earliest         betmgm away   313 157 156  0 -29.52  -7.67  -15.87   1.64 -0.0943
spreads_q1    2026 earliest         betmgm  fav   313 139 174  0 -53.86 -15.22  -24.99  -6.29 -0.1721
spreads_q1    2026 earliest         betmgm  dog   313 174 139  0  -5.26  -1.28   -9.73   7.81 -0.0168
spreads_q1    2026 earliest      betrivers home     3   2   1  0   0.91  27.16 -100.00 102.86  0.3033
spreads_q1    2026 earliest      betrivers away     3   1   2  0  -1.87 -46.87 -100.00  89.29 -0.6233
spreads_q1    2026 earliest      betrivers  fav     3   2   1  0   0.91  27.16 -100.00 102.86  0.3033
spreads_q1    2026 earliest      betrivers  dog     3   1   2  0  -1.87 -46.87 -100.00  89.29 -0.6233
spreads_q1    2026 earliest       fanatics home    64  28  36  0 -14.80 -19.49  -38.89   0.06 -0.2312
spreads_q1    2026 earliest       fanatics away    64  36  28  0   3.90   5.21  -14.29  25.22  0.0609
spreads_q1    2026 earliest       fanatics  fav    64  26  38  0 -17.40 -23.56  -42.12  -3.89 -0.2719
spreads_q1    2026 earliest       fanatics  dog    64  38  26  0   6.50   8.45  -10.38  25.83  0.1016
spreads_q1    2026 earliest    betus (ref) home    10   5   5  0  -1.00  -8.26  -63.33  45.90 -0.1000
spreads_q1    2026 earliest    betus (ref) away    10   5   5  0  -0.90  -7.56  -62.71  46.67 -0.0900
spreads_q1    2026 earliest    betus (ref)  fav    10   5   5  0  -1.00  -8.26  -26.67   9.84 -0.1000
spreads_q1    2026 earliest    betus (ref)  dog    10   5   5  0  -0.90  -7.56  -25.42  10.00 -0.0900
spreads_q1    2026 earliest BEST decidable home   316 153 163  0 -24.99  -7.15  -16.77   1.90 -0.0791
spreads_q1    2026 earliest BEST decidable away   316 163 153  0 -18.69  -4.93  -13.46   4.26 -0.0591
spreads_q1    2026 earliest BEST decidable  fav   316 146 170  0 -38.10 -11.02  -19.59  -2.45 -0.1206
spreads_q1    2026 earliest BEST decidable  dog   316 170 146  0  -5.58  -1.46   -9.59   6.78 -0.0177
spreads_q1    2027     T-10        fanduel home   107  63  44  0  12.97  10.71   -5.27  24.43  0.1212
spreads_q1    2027     T-10        fanduel away   107  44  63  0 -27.59 -22.78  -36.55  -6.73 -0.2579
spreads_q1    2027     T-10        fanduel  fav   107  60  47  0   7.02   5.84   -8.18  20.13  0.0656
spreads_q1    2027     T-10        fanduel  dog   107  47  60  0 -21.64 -17.73  -31.60  -4.02 -0.2022
spreads_q1    2027     T-10         betmgm home     4   3   1  0   3.25  81.25  -35.00 147.50  0.8125
spreads_q1    2027     T-10         betmgm away     4   1   3  0  -5.25 -61.05 -100.00   6.91 -1.3125
spreads_q1    2027     T-10         betmgm  fav     4   3   1  0   3.25  81.25  -35.00 147.50  0.8125
spreads_q1    2027     T-10         betmgm  dog     4   1   3  0  -5.25 -61.05 -100.00   6.91 -1.3125
spreads_q1    2027     T-10      betrivers home   106  63  43  0  11.80   9.34   -6.21  22.31  0.1113
spreads_q1    2027     T-10      betrivers away   106  43  63  0 -32.92 -25.79  -38.68 -10.53 -0.3106
spreads_q1    2027     T-10      betrivers  fav   106  62  44  0  10.81   8.72   -4.30  22.06  0.1020
spreads_q1    2027     T-10      betrivers  dog   106  44  62  0 -31.93 -24.54  -37.61 -12.03 -0.3012
spreads_q1    2027     T-10 BEST decidable home   107  63  44  0  13.26  11.05   -5.00  24.78  0.1239
spreads_q1    2027     T-10 BEST decidable away   107  44  63  0 -28.28 -23.21  -36.78  -7.14 -0.2643
spreads_q1    2027     T-10 BEST decidable  fav   107  61  46  0   9.26   7.75   -6.54  22.30  0.0865
spreads_q1    2027     T-10 BEST decidable  dog   107  46  61  0 -24.28 -19.86  -34.10  -5.84 -0.2269
spreads_q1    2027 earliest        fanduel home   107  63  44  0  12.97  10.66   -5.19  24.42  0.1212
spreads_q1    2027 earliest        fanduel away   107  44  63  0 -27.07 -22.44  -36.22  -6.36 -0.2530
spreads_q1    2027 earliest        fanduel  fav   107  61  46  0   9.14   7.57   -5.54  21.43  0.0854
spreads_q1    2027 earliest        fanduel  dog   107  46  61  0 -23.24 -19.13  -33.19  -5.74 -0.2172
spreads_q1    2027 earliest         betmgm home     5   4   1  0   4.85  97.00   -3.00 150.00  0.9700
spreads_q1    2027 earliest         betmgm away     5   1   4  0  -7.65 -70.18 -100.00 -10.96 -1.5300
spreads_q1    2027 earliest         betmgm  fav     5   4   1  0   4.85  97.00   -3.00 150.00  0.9700
spreads_q1    2027 earliest         betmgm  dog     5   1   4  0  -7.65 -70.18 -100.00 -10.96 -1.5300
spreads_q1    2027 earliest      betrivers home   107  63  44  0  10.11   7.82   -7.19  20.96  0.0945
spreads_q1    2027 earliest      betrivers away   107  44  63  0 -30.40 -23.86  -37.30  -8.25 -0.2841
spreads_q1    2027 earliest      betrivers  fav   107  57  50  0  -1.72  -1.35  -14.66  12.77 -0.0161
spreads_q1    2027 earliest      betrivers  dog   107  50  57  0 -18.57 -14.31  -28.66  -0.85 -0.1736
spreads_q1    2027 earliest BEST decidable home   107  63  44  0  13.82  11.50   -4.12  24.91  0.1292
spreads_q1    2027 earliest BEST decidable away   107  44  63  0 -27.46 -22.48  -36.08  -6.48 -0.2566
spreads_q1    2027 earliest BEST decidable  fav   107  60  47  0   7.50   6.24   -7.63  21.31  0.0701
spreads_q1    2027 earliest BEST decidable  dog   107  47  60  0 -21.14 -17.31  -32.45  -3.16 -0.1976

==== totals_q1 ====
   market  season decision           book  side  bets   W   L  P  units   ret%    lo%    hi%   u/bet
totals_q1    2024     T-10    betus (ref)  over   317 148 169  0 -53.59 -14.18 -22.52  -5.41 -0.1691
totals_q1    2024     T-10    betus (ref) under   317 169 148  0  -7.26  -1.92 -10.76   6.46 -0.0229
totals_q1    2024 earliest    betus (ref)  over   317 149 168  0 -50.92 -13.50 -21.61  -4.76 -0.1606
totals_q1    2024 earliest    betus (ref) under   317 168 149  0  -9.46  -2.50 -11.26   5.58 -0.0298
totals_q1    2025     T-10    betus (ref)  over   247 112 135  0 -50.50 -17.00 -26.04  -6.66 -0.2045
totals_q1    2025     T-10    betus (ref) under   247 135 112  0   1.15   0.39  -9.96   9.58  0.0047
totals_q1    2025 earliest    betus (ref)  over   253 113 140  0 -55.35 -18.19 -27.11  -8.75 -0.2188
totals_q1    2025 earliest    betus (ref) under   253 140 113  0   4.95   1.64  -7.84  10.59  0.0196
totals_q1    2026     T-10        fanduel  over   313 151 162  0 -32.70  -9.16 -16.90  -1.20 -0.1045
totals_q1    2026     T-10        fanduel under   313 162 151  0  -6.13  -1.75  -9.74   6.12 -0.0196
totals_q1    2026     T-10         betmgm  over   222 105 117  0 -36.50 -13.49 -21.48  -5.08 -0.1644
totals_q1    2026     T-10         betmgm under   222 117 105  0  -7.67  -2.88 -11.64   5.30 -0.0345
totals_q1    2026     T-10       fanatics  over    58  27  31  0 -14.25 -16.53 -30.71  -4.05 -0.2457
totals_q1    2026     T-10       fanatics under    58  31  27  0   2.40   3.03 -11.14  19.32  0.0414
totals_q1    2026     T-10    betus (ref)  over    10   6   4  0   1.20  10.00 -26.67  46.67  0.1200
totals_q1    2026     T-10    betus (ref) under    10   4   6  0  -3.20 -26.67 -63.33  10.00 -0.3200
totals_q1    2026     T-10 BEST decidable  over   314 154 160  0 -32.63  -8.88 -16.38  -1.05 -0.1039
totals_q1    2026     T-10 BEST decidable under   314 160 154  0 -10.59  -3.03 -11.22   4.75 -0.0337
totals_q1    2026 earliest        fanduel  over   314 153 161  0 -29.72  -8.30 -15.99  -0.36 -0.0946
totals_q1    2026 earliest        fanduel under   314 161 153  0  -9.52  -2.70 -10.55   5.03 -0.0303
totals_q1    2026 earliest         betmgm  over   224 108 116  0 -33.97 -12.30 -20.85  -3.87 -0.1517
totals_q1    2026 earliest         betmgm under   224 116 108  0 -10.68  -4.03 -12.80   4.71 -0.0477
totals_q1    2026 earliest       fanatics  over    64  29  35  0 -11.75 -15.61 -28.96  -2.47 -0.1836
totals_q1    2026 earliest       fanatics under    64  35  29  0   0.85   1.13 -11.78  14.05  0.0133
totals_q1    2026 earliest    betus (ref)  over    10   7   3  0   3.40  28.33  10.00  46.67  0.3400
totals_q1    2026 earliest    betus (ref) under    10   3   7  0  -5.40 -45.00 -63.33 -26.67 -0.5400
totals_q1    2026 earliest BEST decidable  over   314 154 160  0 -31.91  -8.75 -16.33  -0.80 -0.1016
totals_q1    2026 earliest BEST decidable under   314 160 154  0 -10.02  -2.88 -10.86   4.89 -0.0319
totals_q1    2027     T-10        fanduel  over   107  57  50  0  -0.88  -0.71 -13.92  12.34 -0.0082
totals_q1    2027     T-10        fanduel under   107  50  57  0 -16.30 -13.16 -25.93  -0.05 -0.1523
totals_q1    2027     T-10      betrivers  over   106  55  51  0  -6.51  -5.08 -15.88   5.08 -0.0614
totals_q1    2027     T-10      betrivers under   106  51  55  0 -14.25 -11.33 -22.12  -0.22 -0.1344
totals_q1    2027     T-10 BEST decidable  over   107  57  50  0  -1.00  -0.80 -13.94  11.98 -0.0093
totals_q1    2027     T-10 BEST decidable under   107  50  57  0 -14.63 -12.06 -25.02   1.18 -0.1367
totals_q1    2027 earliest        fanduel  over   107  57  50  0  -0.88  -0.71 -13.92  12.34 -0.0082
totals_q1    2027 earliest        fanduel under   107  50  57  0 -16.30 -13.16 -25.93  -0.05 -0.1523
totals_q1    2027 earliest      betrivers  over   107  59  48  0   1.14   0.88 -12.94  13.98  0.0107
totals_q1    2027 earliest      betrivers under   107  48  59  0 -22.02 -17.33 -30.51  -3.57 -0.2058
totals_q1    2027 earliest BEST decidable  over   107  59  48  0   1.14   0.88 -12.94  13.98  0.0107
totals_q1    2027 earliest BEST decidable under   107  48  59  0 -22.02 -17.33 -30.51  -3.57 -0.2058

==== h2h_q1 ====
market  season decision           book side  bets   W   L  P  units    ret%     lo%     hi%   u/bet
h2h_q1    2024     T-10    betus (ref) home   273 138 114 21 -27.14   -6.94  -15.67    1.71 -0.0994
h2h_q1    2024     T-10    betus (ref) away   273 114 138 21 -20.84   -7.16  -17.91    3.76 -0.0763
h2h_q1    2024     T-10    betus (ref)  fav   244 132  94 18 -28.06   -7.23  -14.25    0.02 -0.1150
h2h_q1    2024     T-10    betus (ref)  dog   244  94 132 18 -14.72   -6.35  -16.60    3.57 -0.0603
h2h_q1    2024 earliest    betus (ref) home   283 142 119 22 -28.41   -7.12  -15.46    1.23 -0.1004
h2h_q1    2024 earliest    betus (ref) away   283 119 142 22 -21.58   -7.20  -17.53    3.18 -0.0763
h2h_q1    2024 earliest    betus (ref)  fav   248 135  93 20 -22.58   -5.86  -13.14    1.35 -0.0911
h2h_q1    2024 earliest    betus (ref)  dog   248  93 135 20 -20.81   -8.90  -18.87    1.30 -0.0839
h2h_q1    2025     T-10    betus (ref) home    89  48  37  4  -3.64   -2.63  -15.08   10.87 -0.0409
h2h_q1    2025     T-10    betus (ref) away    89  37  48  4 -12.83  -12.08  -27.29    3.00 -0.1442
h2h_q1    2025     T-10    betus (ref)  fav    88  47  37  4 -17.46  -11.06  -23.76    2.95 -0.1984
h2h_q1    2025     T-10    betus (ref)  dog    88  37  47  4   1.19    1.41  -20.65   21.34  0.0135
h2h_q1    2025 earliest    betus (ref) home    94  52  38  4  -1.07   -0.73  -13.56   13.11 -0.0114
h2h_q1    2025 earliest    betus (ref) away    94  38  52  4 -15.92  -14.35  -30.95    1.01 -0.1694
h2h_q1    2025 earliest    betus (ref)  fav    93  52  37  4 -13.04   -7.80  -21.55    7.00 -0.1403
h2h_q1    2025 earliest    betus (ref)  dog    93  37  52  4  -3.75   -4.19  -27.29   16.93 -0.0403
h2h_q1    2026     T-10         betmgm home     3   2   1  0   0.10    2.03 -100.00   66.01  0.0333
h2h_q1    2026     T-10         betmgm away     3   1   2  0  -0.90  -28.13 -100.00  130.00 -0.3000
h2h_q1    2026     T-10         betmgm  fav     3   1   2  0  -2.10  -42.42 -100.00   -6.56 -0.7000
h2h_q1    2026     T-10         betmgm  dog     3   2   1  0   1.30   40.88    0.00  130.00  0.4333
h2h_q1    2026     T-10      betrivers home   316 168 133 15 -30.10   -6.15  -15.62    2.32 -0.0952
h2h_q1    2026     T-10      betrivers away   316 133 168 15 -24.22   -6.96  -17.57    5.19 -0.0766
h2h_q1    2026     T-10      betrivers  fav   313 167 131 15 -57.38  -10.84  -18.27   -2.76 -0.1833
h2h_q1    2026     T-10      betrivers  dog   313 131 167 15   3.48    1.16  -10.96   12.34  0.0111
h2h_q1    2026     T-10    betus (ref) home     4   3   0  1   3.00   47.24   47.24   47.24  0.7500
h2h_q1    2026     T-10    betus (ref) away     4   0   3  1  -3.00 -100.00 -100.00 -100.00 -0.7500
h2h_q1    2026     T-10    betus (ref)  fav     4   3   0  1   3.00   47.24   47.24   47.24  0.7500
h2h_q1    2026     T-10    betus (ref)  dog     4   0   3  1  -3.00 -100.00 -100.00 -100.00 -0.7500
h2h_q1    2026     T-10 BEST decidable home   316 168 133 15 -29.95   -6.12  -15.62    2.37 -0.0948
h2h_q1    2026     T-10 BEST decidable away   316 133 168 15 -24.22   -6.96  -17.57    5.19 -0.0766
h2h_q1    2026     T-10 BEST decidable  fav   314 167 132 15 -58.37  -11.01  -18.47   -2.94 -0.1859
h2h_q1    2026     T-10 BEST decidable  dog   314 132 167 15   4.48    1.48  -10.58   12.80  0.0143
h2h_q1    2026 earliest         betmgm home     3   2   1  0   0.00    0.00 -100.00   72.73  0.0000
h2h_q1    2026 earliest         betmgm away     3   1   2  0  -0.83  -26.10 -100.00  135.00 -0.2767
h2h_q1    2026 earliest         betmgm  fav     3   2   1  0   0.00    0.00 -100.00   72.73  0.0000
h2h_q1    2026 earliest         betmgm  dog     3   1   2  0  -0.83  -26.10 -100.00  135.00 -0.2767
h2h_q1    2026 earliest      betrivers home   316 168 133 15 -29.37   -6.04  -15.48    2.48 -0.0930
h2h_q1    2026 earliest      betrivers away   316 133 168 15 -24.70   -7.12  -17.73    5.10 -0.0782
h2h_q1    2026 earliest      betrivers  fav   316 169 132 15 -54.65  -10.36  -17.88   -2.26 -0.1730
h2h_q1    2026 earliest      betrivers  dog   316 132 169 15   0.58    0.19  -11.74   11.42  0.0018
h2h_q1    2026 earliest    betus (ref) home     4   3   0  1   3.00   46.51   46.51   46.51  0.7500
h2h_q1    2026 earliest    betus (ref) away     4   0   3  1  -3.00 -100.00 -100.00 -100.00 -0.7500
h2h_q1    2026 earliest    betus (ref)  fav     4   3   0  1   3.00   46.51   46.51   46.51  0.7500
h2h_q1    2026 earliest    betus (ref)  dog     4   0   3  1  -3.00 -100.00 -100.00 -100.00 -0.7500
h2h_q1    2026 earliest BEST decidable home   316 168 133 15 -28.92   -5.95  -15.41    2.51 -0.0915
h2h_q1    2026 earliest BEST decidable away   316 133 168 15 -24.70   -7.12  -17.73    5.10 -0.0782
h2h_q1    2026 earliest BEST decidable  fav   316 169 132 15 -54.20  -10.28  -17.75   -2.18 -0.1715
h2h_q1    2026 earliest BEST decidable  dog   316 132 169 15   0.58    0.19  -11.74   11.42  0.0018
h2h_q1    2027     T-10         betmgm home   104  62  38  4   8.03    5.18   -7.65   15.90  0.0772
h2h_q1    2027     T-10         betmgm away   104  38  62  4 -28.21  -24.15  -37.21   -9.31 -0.2712
h2h_q1    2027     T-10         betmgm  fav   103  61  38  4  -1.55   -0.92  -11.60   10.40 -0.0150
h2h_q1    2027     T-10         betmgm  dog   103  38  61  4 -18.43  -18.23  -33.42   -3.59 -0.1789
h2h_q1    2027     T-10      betrivers home   106  63  39  4   9.40    6.10   -6.43   17.78  0.0887
h2h_q1    2027     T-10      betrivers away   106  39  63  4 -29.18  -24.27  -37.98   -9.87 -0.2753
h2h_q1    2027     T-10      betrivers  fav   106  64  38  4   2.30    1.36   -8.75   12.01  0.0217
h2h_q1    2027     T-10      betrivers  dog   106  38  64  4 -22.08  -20.91  -34.62   -7.59 -0.2083
h2h_q1    2027     T-10 BEST decidable home   107  63  40  4   8.80    5.73   -7.10   17.30  0.0822
h2h_q1    2027     T-10 BEST decidable away   107  40  63  4 -26.21  -22.03  -35.71   -7.10 -0.2450
h2h_q1    2027     T-10 BEST decidable  fav   107  63  40  4   0.14    0.08  -10.79   11.31  0.0013
h2h_q1    2027     T-10 BEST decidable  dog   107  40  63  4 -17.55  -16.68  -31.52   -2.24 -0.1640
h2h_q1    2027 earliest         betmgm home   104  62  38  4   6.63    4.24   -8.56   15.39  0.0638
h2h_q1    2027 earliest         betmgm away   104  38  62  4 -27.97  -24.11  -37.43   -8.94 -0.2689
h2h_q1    2027 earliest         betmgm  fav   103  59  40  4  -6.80   -4.02  -14.69    7.21 -0.0660
h2h_q1    2027 earliest         betmgm  dog   103  40  59  4 -14.34  -14.21  -29.67    0.27 -0.1392
h2h_q1    2027 earliest      betrivers home   107  63  40  4   6.54    4.15   -8.47   15.89  0.0612
h2h_q1    2027 earliest      betrivers away   107  40  63  4 -27.40  -22.70  -36.20   -7.83 -0.2561
h2h_q1    2027 earliest      betrivers  fav   106  60  42  4  -7.41   -4.35  -14.89    6.71 -0.0699
h2h_q1    2027 earliest      betrivers  dog   106  42  60  4 -13.25  -12.57  -27.72    1.42 -0.1250
h2h_q1    2027 earliest BEST decidable home   107  63  40  4   7.25    4.65   -8.17   16.47  0.0678
h2h_q1    2027 earliest BEST decidable away   107  40  63  4 -25.94  -21.88  -35.55   -6.64 -0.2424
h2h_q1    2027 earliest BEST decidable  fav   107  61  42  4  -5.28   -3.12  -13.48    7.77 -0.0493
h2h_q1    2027 earliest BEST decidable  dog   107  42  61  4 -13.41  -12.74  -27.66    1.32 -0.1253

==== pooled over seasons: BEST decidable (2025-26 + 2026-27) and offshore reference (every season) ====
    market decision             book  side  bets   W   L  P   units   ret%    lo%   hi%
spreads_h1     T-10   BEST decidable  home   423 211 212  0  -25.70  -5.43 -13.30  2.83
spreads_h1     T-10   BEST decidable  away   423 212 211  0  -33.56  -6.80 -14.50  0.88
spreads_h1     T-10   BEST decidable   fav   423 200 223  0  -50.67 -10.65 -17.21 -3.55
spreads_h1     T-10   BEST decidable   dog   423 223 200  0   -8.59  -1.75  -8.59  4.70
spreads_h1     T-10      betus (ref)  home  1088 542 530 16  -85.38  -6.73 -10.69 -2.62
spreads_h1     T-10      betus (ref)  away  1088 530 542 16 -111.44  -8.80 -12.92 -4.75
spreads_h1     T-10      betus (ref)   fav  1082 501 565 16 -168.36 -13.33 -18.15 -9.06
spreads_h1     T-10      betus (ref)   dog  1082 565 501 16  -27.30  -2.17  -6.47  2.64
spreads_h1     T-10     gtbets (ref)  home   777 397 369 11  -27.92  -3.15  -8.37  2.21
spreads_h1     T-10     gtbets (ref)  away   777 369 397 11  -85.51  -9.72 -15.06 -4.43
spreads_h1     T-10     gtbets (ref)   fav   757 352 394 11  -98.71 -11.54 -17.64 -6.07
spreads_h1     T-10     gtbets (ref)   dog   757 394 352 11  -11.77  -1.36  -6.83  4.71
spreads_h1     T-10 mybookieag (ref)  home   141  69  70  2  -13.56  -8.26 -22.33  4.04
spreads_h1     T-10 mybookieag (ref)  away   141  70  69  2  -10.54  -6.49 -18.80  7.57
spreads_h1     T-10 mybookieag (ref)   fav   137  66  69  2  -14.56  -9.22 -20.61  2.29
spreads_h1     T-10 mybookieag (ref)   dog   137  69  66  2   -8.78  -5.51 -16.87  5.81
spreads_h1 earliest   BEST decidable  home   423 208 215  0  -30.98  -6.56 -13.82  1.01
spreads_h1 earliest   BEST decidable  away   423 215 208  0  -27.00  -5.46 -12.92  1.63
spreads_h1 earliest   BEST decidable   fav   423 199 224  0  -51.11 -10.78 -17.33 -3.72
spreads_h1 earliest   BEST decidable   dog   423 224 199  0   -6.87  -1.39  -8.34  4.80
spreads_h1 earliest      betus (ref)  home  1096 552 523 21  -68.30  -5.36  -9.56 -1.08
spreads_h1 earliest      betus (ref)  away  1096 523 552 21 -130.32 -10.26 -14.55 -6.10
spreads_h1 earliest      betus (ref)   fav  1095 526 548 21 -124.11  -9.76 -14.24 -5.28
spreads_h1 earliest      betus (ref)   dog  1095 548 526 21  -74.36  -5.86 -10.32 -1.30
spreads_h1 earliest     gtbets (ref)  home   782 400 374  8  -28.43  -3.20  -8.31  2.45
spreads_h1 earliest     gtbets (ref)  away   782 374 400  8  -86.59  -9.69 -15.38 -4.53
spreads_h1 earliest     gtbets (ref)   fav   769 367 394  8  -83.33  -9.55 -15.69 -3.82
spreads_h1 earliest     gtbets (ref)   dog   769 394 367  8  -29.65  -3.37  -9.00  2.64
spreads_h1 earliest mybookieag (ref)  home   180  90  90  0  -15.52  -7.33 -18.68  3.90
spreads_h1 earliest mybookieag (ref)  away   180  90  90  0  -15.23  -7.21 -18.53  4.35
spreads_h1 earliest mybookieag (ref)   fav   174  86  88  0  -17.04  -8.34 -19.37  2.21
spreads_h1 earliest mybookieag (ref)   dog   174  88  86  0  -12.69  -6.21 -17.08  4.87
 totals_h1     T-10   BEST decidable  over   423 216 207  0  -27.86  -5.58 -12.38  1.25
 totals_h1     T-10   BEST decidable under   423 207 216  0  -36.00  -7.54 -14.60 -0.57
 totals_h1     T-10      betus (ref)  over  1096 546 531 19  -81.50  -6.41 -10.91 -1.82
 totals_h1     T-10      betus (ref) under  1096 531 546 19 -116.31  -9.11 -13.80 -4.55
 totals_h1     T-10     gtbets (ref)  over   776 381 390  5  -68.07  -7.68 -13.03 -2.37
 totals_h1     T-10     gtbets (ref) under   776 390 381  5  -50.03  -5.63 -10.98 -0.33
 totals_h1     T-10 mybookieag (ref)  over   141  75  66  0   -2.30  -1.39 -13.77 11.70
 totals_h1     T-10 mybookieag (ref) under   141  66  75  0  -22.32 -13.45 -26.52 -1.20
 totals_h1 earliest   BEST decidable  over   423 218 205  0  -22.91  -4.62 -11.67  2.29
 totals_h1 earliest   BEST decidable under   423 205 218  0  -41.46  -8.68 -15.94 -1.57
 totals_h1 earliest      betus (ref)  over  1100 553 529 18  -72.79  -5.69 -10.27 -0.91
 totals_h1 earliest      betus (ref) under  1100 529 553 18 -125.86  -9.82 -14.54 -5.21
 totals_h1 earliest     gtbets (ref)  over   782 389 387  6  -55.07  -6.18 -11.10 -0.83
 totals_h1 earliest     gtbets (ref) under   782 387 389  6  -61.84  -6.90 -12.30 -2.01
 totals_h1 earliest mybookieag (ref)  over   180  97  81  2    2.18   1.05  -9.17 11.08
 totals_h1 earliest mybookieag (ref) under   180  81  97  2  -33.15 -15.82 -25.80 -5.68
    h2h_h1     T-10   BEST decidable  home   465 260 190 15  -23.79  -3.08  -8.77  2.87
    h2h_h1     T-10   BEST decidable  away   465 190 260 15  -39.05  -7.39 -15.60  0.70
    h2h_h1     T-10   BEST decidable   fav   465 258 192 15  -81.98  -9.67 -14.56 -4.29
    h2h_h1     T-10   BEST decidable   dog   465 192 258 15   19.14   4.22  -4.64 12.35
    h2h_h1     T-10      betus (ref)  home   759 436 297 26  -66.14  -4.79  -9.30 -0.50
    h2h_h1     T-10      betus (ref)  away   759 297 436 26  -88.90 -10.11 -16.32 -3.65
    h2h_h1     T-10      betus (ref)   fav   747 459 264 24  -79.80  -5.30  -9.54 -1.08
    h2h_h1     T-10      betus (ref)   dog   747 264 459 24  -73.24 -10.01 -17.26 -2.51
    h2h_h1     T-10     gtbets (ref)  home   784 442 316 26  -58.32  -4.36  -8.64  0.27
    h2h_h1     T-10     gtbets (ref)  away   784 316 442 26  -99.02 -10.97 -17.20 -5.06
    h2h_h1     T-10     gtbets (ref)   fav   773 435 312 26 -141.46  -9.70 -13.88 -5.90
    h2h_h1     T-10     gtbets (ref)   dog   773 312 435 26  -14.23  -1.88  -8.15  4.92
    h2h_h1     T-10 mybookieag (ref)  home   141  79  54  8   -4.14  -1.81 -13.99  9.38
    h2h_h1     T-10 mybookieag (ref)  away   141  54  79  8  -17.78 -11.64 -26.37  5.29
    h2h_h1     T-10 mybookieag (ref)   fav   140  81  51  8   -8.44  -3.45 -11.61  4.03
    h2h_h1     T-10 mybookieag (ref)   dog   140  51  81  8  -13.30  -9.96 -21.63  2.35
    h2h_h1 earliest   BEST decidable  home   465 260 190 15  -25.67  -3.31  -8.93  2.72
    h2h_h1 earliest   BEST decidable  away   465 190 260 15  -39.94  -7.62 -15.81  0.39
    h2h_h1 earliest   BEST decidable   fav   463 258 190 15  -76.56  -9.06 -14.04 -3.85
    h2h_h1 earliest   BEST decidable   dog   463 190 258 15   11.28   2.50  -6.30 10.83
    h2h_h1 earliest      betus (ref)  home   806 462 315 29  -62.55  -4.34  -8.93 -0.20
    h2h_h1 earliest      betus (ref)  away   806 315 462 29  -98.58 -10.62 -16.71 -4.16
    h2h_h1 earliest      betus (ref)   fav   785 479 278 28  -77.39  -4.98  -9.07 -0.95
    h2h_h1 earliest      betus (ref)   dog   785 278 479 28  -79.75 -10.39 -17.07 -3.43
    h2h_h1 earliest     gtbets (ref)  home   784 442 316 26  -55.65  -4.18  -8.42  0.45
    h2h_h1 earliest     gtbets (ref)  away   784 316 442 26  -99.72 -11.12 -17.29 -5.19
    h2h_h1 earliest     gtbets (ref)   fav   766 434 307 25 -129.76  -9.01 -13.11 -5.16
    h2h_h1 earliest     gtbets (ref)   dog   766 307 434 25  -23.06  -3.08  -9.33  3.71
    h2h_h1 earliest mybookieag (ref)  home   180  99  73  8  -15.68  -5.23 -15.53  4.91
    h2h_h1 earliest mybookieag (ref)  away   180  73  99  8  -16.62  -8.35 -21.94  5.22
    h2h_h1 earliest mybookieag (ref)   fav   180 105  67  8  -15.92  -4.91 -13.04  3.29
    h2h_h1 earliest mybookieag (ref)   dog   180  67 105  8  -16.38  -9.38 -21.95  2.90
spreads_q1     T-10   BEST decidable  home   423 219 204  0   -8.00  -1.69  -9.72  6.10
spreads_q1     T-10   BEST decidable  away   423 204 219  0  -52.67 -10.54 -18.08 -2.54
spreads_q1     T-10   BEST decidable   fav   423 207 216  0  -30.73  -6.57 -14.08  0.78
spreads_q1     T-10   BEST decidable   dog   423 216 207  0  -29.94  -5.92 -13.00  1.28
spreads_q1     T-10      betus (ref)  home   571 292 279  0  -40.23  -5.89 -12.27  0.31
spreads_q1     T-10      betus (ref)  away   571 279 292  0  -68.48 -10.04 -16.24 -3.64
spreads_q1     T-10      betus (ref)   fav   569 273 296  0  -80.17 -11.77 -17.61 -5.64
spreads_q1     T-10      betus (ref)   dog   569 296 273  0  -28.14  -4.15 -10.33  1.68
spreads_q1 earliest   BEST decidable  home   423 216 207  0  -11.17  -2.38 -10.42  5.43
spreads_q1 earliest   BEST decidable  away   423 207 216  0  -46.15  -9.20 -16.91 -1.54
spreads_q1 earliest   BEST decidable   fav   423 206 217  0  -30.60  -6.57 -13.84  1.11
spreads_q1 earliest   BEST decidable   dog   423 217 206  0  -26.72  -5.29 -12.85  1.67
spreads_q1 earliest      betus (ref)  home   578 298 280  0  -36.55  -5.28 -11.24  0.64
spreads_q1 earliest      betus (ref)  away   578 280 298  0  -74.23 -10.79 -16.73 -4.90
spreads_q1 earliest      betus (ref)   fav   577 279 298  0  -77.56 -11.20 -16.60 -5.43
spreads_q1 earliest      betus (ref)   dog   577 298 279  0  -33.02  -4.81 -10.54  0.56
 totals_q1     T-10   BEST decidable  over   421 211 210  0  -33.63  -6.83 -13.27 -0.54
 totals_q1     T-10   BEST decidable under   421 210 211  0  -25.22  -5.36 -11.88  1.27
 totals_q1     T-10      betus (ref)  over   574 266 308  0 -102.89 -14.98 -21.05 -7.89
 totals_q1     T-10      betus (ref) under   574 308 266  0   -9.31  -1.36  -8.40  4.72
 totals_q1 earliest   BEST decidable  over   421 213 208  0  -30.77  -6.22 -12.86  0.39
 totals_q1 earliest   BEST decidable under   421 208 213  0  -32.04  -6.74 -13.50 -0.12
 totals_q1 earliest      betus (ref)  over   580 269 311  0 -102.87 -14.83 -21.37 -8.51
 totals_q1 earliest      betus (ref) under   580 311 269  0   -9.91  -1.43  -7.78  5.07
    h2h_q1     T-10   BEST decidable  home   423 231 173 19  -21.15  -3.29 -10.36  3.67
    h2h_q1     T-10   BEST decidable  away   423 173 231 19  -50.43 -10.80 -19.39 -2.00
    h2h_q1     T-10   BEST decidable   fav   421 230 172 19  -58.23  -8.35 -14.46 -1.98
    h2h_q1     T-10   BEST decidable   dog   421 172 230 19  -13.07  -3.21 -12.66  5.75
    h2h_q1     T-10      betus (ref)  home   366 189 151 26  -27.78  -5.18 -12.31  2.07
    h2h_q1     T-10      betus (ref)  away   366 151 189 26  -36.67  -9.16 -17.97 -0.46
    h2h_q1     T-10      betus (ref)   fav   336 182 131 23  -42.52  -7.70 -13.79 -0.94
    h2h_q1     T-10      betus (ref)   dog   336 131 182 23  -16.53  -5.18 -14.85  3.55
    h2h_q1 earliest   BEST decidable  home   423 231 173 19  -21.67  -3.38 -10.33  3.59
    h2h_q1 earliest   BEST decidable  away   423 173 231 19  -50.64 -10.88 -19.47 -1.99
    h2h_q1 earliest   BEST decidable   fav   423 230 174 19  -59.48  -8.54 -14.49 -2.30
    h2h_q1 earliest   BEST decidable   dog   423 174 230 19  -12.83  -3.13 -12.10  5.58
    h2h_q1 earliest      betus (ref)  home   381 197 157 27  -26.49  -4.78 -11.20  2.38
    h2h_q1 earliest      betus (ref)  away   381 157 197 27  -40.50  -9.79 -18.70 -1.94
    h2h_q1 earliest      betus (ref)   fav   345 190 130 25  -32.63  -5.83 -12.17  0.58
    h2h_q1 earliest      betus (ref)   dog   345 130 190 25  -27.56  -8.45 -17.73  0.48

==== moneyline favourite / underdog at the best decidable price, T-10, by price band ====
market  season side          band  bets  W  L  P  units    ret%     lo%     hi%
h2h_h1    2026  fav (-5000, -300]    25 21  3  1   8.93   12.41   -1.90   24.41
h2h_h1    2026  fav  (-300, -200]   116 70 44  2 -32.30  -12.03  -21.45   -3.13
h2h_h1    2026  fav  (-200, -150]   105 55 46  4 -25.47  -14.43  -28.60   -0.14
h2h_h1    2026  fav  (-150, -100]   112 48 60  4 -29.24  -20.85  -33.34   -8.12
h2h_h1    2026  dog  (-150, -100]    38 23 15  0   7.04   17.47   -6.20   41.59
h2h_h1    2026  dog   (-100, 100]     7  3  4  0  -1.00  -14.29  -71.43   42.86
h2h_h1    2026  dog    (100, 150]   155 68 79  8   2.82    1.92  -13.78   17.22
h2h_h1    2026  dog    (150, 200]    83 36 45  2  18.61   22.98   -0.44   48.49
h2h_h1    2026  dog    (200, 300]    62 23 38  1  14.80   24.26   -7.31   54.64
h2h_h1    2026  dog   (300, 5000]    13  0 13  0 -13.00 -100.00 -100.00 -100.00
h2h_h1    2027  fav (-5000, -300]     7  7  0  0   5.43   25.87   23.06   28.63
h2h_h1    2027  fav  (-300, -200]    29 19  9  1  -2.75   -4.07  -25.30   20.56
h2h_h1    2027  fav  (-200, -150]    34 20 13  1  -2.89   -5.07  -26.89   13.57
h2h_h1    2027  fav  (-150, -100]    37 18 17  2  -3.70   -8.19  -31.01   20.85
h2h_h1    2027  dog  (-150, -100]    15 10  5  0   4.71   29.92  -10.54   68.83
h2h_h1    2027  dog   (-100, 100]     1  0  1  0  -1.00 -100.00 -100.00 -100.00
h2h_h1    2027  dog    (100, 150]    49 17 30  2  -8.50  -18.09  -42.14    7.36
h2h_h1    2027  dog    (150, 200]    25  9 15  1   0.66    2.75  -42.39   54.97
h2h_h1    2027  dog    (200, 300]    12  3  8  1  -1.00   -9.09  -72.08   68.00
h2h_h1    2027  dog   (300, 5000]     5  0  5  0  -5.00 -100.00 -100.00 -100.00
h2h_q1    2026  fav (-5000, -300]     8  5  3  0  -4.53  -18.87  -51.93   13.70
h2h_q1    2026  fav  (-300, -200]    93 55 32  6 -17.63   -8.78  -19.58    2.12
h2h_q1    2026  fav  (-200, -150]   100 55 40  5 -13.86   -8.51  -23.23    5.69
h2h_q1    2026  fav  (-150, -100]   113 52 57  4 -22.35  -15.67  -28.83   -2.16
h2h_q1    2026  dog  (-150, -100]    44 25 17  2   6.67   14.72  -12.57   39.13
h2h_q1    2026  dog   (-100, 100]    10  5  5  0   0.00    0.00  -45.45   45.45
h2h_q1    2026  dog    (100, 150]   172 71 94  7  -6.44   -3.90  -19.28   11.99
h2h_q1    2026  dog    (150, 200]    73 26 41  6   2.80    4.18  -19.05   29.42
h2h_q1    2026  dog    (200, 300]    15  5 10  0   1.45    9.67  -54.29   73.69
h2h_q1    2027  fav (-5000, -300]     1  0  1  0  -3.00 -100.00 -100.00 -100.00
h2h_q1    2027  fav  (-300, -200]    17 13  4  0   4.15   10.88  -10.64   30.16
h2h_q1    2027  fav  (-200, -150]    43 25 16  2  -1.25   -1.84  -14.83   10.68
h2h_q1    2027  fav  (-150, -100]    46 25 19  2   0.24    0.41  -17.31   18.78
h2h_q1    2027  dog  (-150, -100]    31 14 16  1  -3.15   -9.77  -33.25   14.04
h2h_q1    2027  dog   (-100, 100]     5  2  3  0  -1.00  -20.00 -100.00   34.17
h2h_q1    2027  dog    (100, 150]    62 21 38  3 -13.05  -22.12  -41.48   -1.98
h2h_q1    2027  dog    (150, 200]     8  2  6  0  -2.50  -31.25 -100.00   40.00
h2h_q1    2027  dog    (200, 300]     1  1  0  0   2.15  215.00  215.00  215.00

==== the five best and five worst cells with 100+ bets ====
    market  season decision           book side  bets   W   L  P  units   ret%    lo%    hi%   u/bet  bh10
    h2h_h1    2026 earliest      betrivers  dog   313 135 168 10  28.72   9.41  -1.60  21.09  0.0918 False
spreads_q1    2027 earliest        fanduel home   107  63  44  0  12.97  10.66  -5.19  24.42  0.1212 False
spreads_q1    2027     T-10        fanduel home   107  63  44  0  12.97  10.71  -5.27  24.43  0.1212 False
spreads_q1    2027     T-10 BEST decidable home   107  63  44  0  13.26  11.05  -5.00  24.78  0.1239 False
spreads_q1    2027 earliest BEST decidable home   107  63  44  0  13.82  11.50  -4.12  24.91  0.1292 False
spreads_q1    2027     T-10      betrivers away   106  43  63  0 -32.92 -25.79 -38.68 -10.53 -0.3106 False
    h2h_h1    2027 earliest      betrivers  dog   107  34  69  4 -26.37 -25.08 -36.56 -13.90 -0.2464 False
spreads_q1    2027     T-10      betrivers  dog   106  44  62  0 -31.93 -24.54 -37.61 -12.03 -0.3012 False
    h2h_q1    2027     T-10      betrivers away   106  39  63  4 -29.18 -24.27 -37.98  -9.87 -0.2753 False
    h2h_q1    2027     T-10         betmgm away   104  38  62  4 -28.21 -24.15 -37.21  -9.31 -0.2712 False
```

## 5. The market's own accuracy, and the half against the full game (task 3)

**(a)** De-vigged proportionally, the spread and total closes score like a coin
flip at their own number (log loss 0.689-0.696 against 0.6931; Fanatics' few
rung quotes aside), as a main line priced near 50/50 should. The moneyline closes score 0.634-0.670 (first half)
and 0.660-0.681 (first quarter). The close is not measurably sharper than the
earliest mark on the same games (differences within about 0.007, Fanatics
aside). Pooled at
the decidable books, the moneyline's calibration slope (result on de-vigged
probability) is 0.877 for the first half and 0.751 for the first quarter: below
1, i.e. the close prices favourites too short, which agrees with the
favourite-underdog asymmetry in section 4. The slope column is not meaningful
for spreads and totals, whose probabilities cluster within a few points of 50%.

**(b)** **The books set the first-half total at 50.05-50.29% of the full-game
total and the first-quarter total at 25.07-25.37%**, with a standard deviation
of 0.2-0.3 percentage points a season, and their period number strays only
0.23-0.55 points from its own straight line off the full game. The results
centre on the same fractions (first half 49.87-50.68%, first quarter
24.75-25.63%), but their slope on the full-game total is noisier and steeper:
0.55, 0.57, 0.72 and 0.53 by season against the books' 0.49-0.50. 2025-26's
0.72 is the outlier that drives the V1 result below. First-half spreads are
0.52-0.54 of the full-game spread at the books (results 0.40-0.55), first
quarter 0.25-0.28 (results 0.18-0.39). By full-game band nothing stands out
beyond noise, with one band read worth a later look: where Pinnacle has the
home club as an underdog by 0-4 points, the home club covered the first-half
number in 58.9% of 175 games (found after looking; a hypothesis, section 10).

Printed by `scripts/euroleague_research/r1_accuracy.py`:

```
==== (a) the close (T-10) against the earliest mark, same games, by market, season and book ====
a_rate = share of side a (home cover / over / home win) among graded; bias = result minus line
    market  season             book  games  a_rate  ll_close  ll_early  brier_close  brier_early  ll_coin  bias  mean_ovr
spreads_h1    2024      betus (ref)    308   0.523    0.6934    0.6932       0.2501       0.2500   0.6931  0.17    1.0888
spreads_h1    2025      betus (ref)    293   0.526    0.6934    0.6936       0.2501       0.2502   0.6931  0.10    1.0809
spreads_h1    2025     gtbets (ref)    274   0.547    0.6895    0.6903       0.2482       0.2486   0.6931  0.34    1.0698
spreads_h1    2026           betmgm    314   0.494    0.6918    0.6923       0.2493       0.2496   0.6931 -0.26    1.0899
spreads_h1    2026      betus (ref)    362   0.467    0.6932    0.6947       0.2500       0.2508   0.6931 -0.39    1.0824
spreads_h1    2026         fanatics     26   0.423    0.5818    0.7025       0.1955       0.2547   0.6931 -2.77    1.0715
spreads_h1    2026          fanduel    313   0.486    0.6937    0.6943       0.2503       0.2506   0.6931 -0.33    1.0605
spreads_h1    2026     gtbets (ref)    392   0.487    0.6931    0.6939       0.2500       0.2504   0.6931 -0.23    1.0698
spreads_h1    2026 mybookieag (ref)     41   0.366    0.6950    0.6932       0.2509       0.2500   0.6931 -1.02    1.0802
spreads_h1    2027           betmgm     47   0.426    0.6891    0.6848       0.2479       0.2458   0.6931 -0.93    1.0891
spreads_h1    2027        betrivers    106   0.557    0.6935    0.6897       0.2502       0.2483   0.6931  1.60    1.0889
spreads_h1    2027      betus (ref)     99   0.545    0.6951    0.6937       0.2510       0.2503   0.6931  1.42    1.0800
spreads_h1    2027          fanduel    107   0.551    0.6929    0.6917       0.2499       0.2493   0.6931  1.45    1.0603
spreads_h1    2027     gtbets (ref)     96   0.552    0.6939    0.6922       0.2504       0.2495   0.6931  1.64    1.0699
spreads_h1    2027 mybookieag (ref)     98   0.551    0.6917    0.6935       0.2493       0.2502   0.6931  1.62    1.0800
 totals_h1    2024      betus (ref)    309   0.505    0.6935    0.6933       0.2502       0.2501   0.6931  0.48    1.0888
 totals_h1    2025      betus (ref)    295   0.492    0.6925    0.6931       0.2497       0.2500   0.6931 -0.01    1.0814
 totals_h1    2025     gtbets (ref)    274   0.482    0.6962    0.6933       0.2515       0.2501   0.6931  0.16    1.0698
 totals_h1    2026           betmgm    313   0.505    0.6921    0.6938       0.2495       0.2503   0.6931  0.79    1.0917
 totals_h1    2026      betus (ref)    361   0.529    0.6932    0.6935       0.2500       0.2502   0.6931  0.60    1.0829
 totals_h1    2026         fanatics     29   0.517    0.6542    0.6915       0.2310       0.2492   0.6931  0.22    1.0688
 totals_h1    2026          fanduel    314   0.510    0.6933    0.6944       0.2501       0.2506   0.6931  0.48    1.0607
 totals_h1    2026     gtbets (ref)    399   0.506    0.6934    0.6932       0.2501       0.2500   0.6931  0.12    1.0699
 totals_h1    2026 mybookieag (ref)     41   0.634    0.6932    0.6904       0.2500       0.2486   0.6931  2.00    1.0796
 totals_h1    2027        betrivers    106   0.500    0.6887    0.6960       0.2478       0.2514   0.6931 -0.57    1.0887
 totals_h1    2027      betus (ref)    104   0.490    0.6952    0.6927       0.2510       0.2498   0.6931 -0.59    1.0792
 totals_h1    2027          fanduel    107   0.486    0.6916    0.6947       0.2492       0.2508   0.6931 -0.52    1.0605
 totals_h1    2027     gtbets (ref)     94   0.489    0.6914    0.6931       0.2491       0.2500   0.6931 -0.44    1.0700
 totals_h1    2027 mybookieag (ref)     98   0.500    0.6935    0.6927       0.2502       0.2498   0.6931 -0.35    1.0800
    h2h_h1    2024      betus (ref)    254   0.618    0.6341    0.6335       0.2214       0.2210   0.6931   NaN    1.0754
    h2h_h1    2025      betus (ref)    188   0.574    0.6491    0.6518       0.2288       0.2299   0.6931   NaN    1.0737
    h2h_h1    2025     gtbets (ref)    275   0.593    0.6496    0.6515       0.2292       0.2300   0.6931   NaN    1.0694
    h2h_h1    2026           betmgm    345   0.565    0.6689    0.6677       0.2385       0.2379   0.6931   NaN    1.0905
    h2h_h1    2026        betrivers    306   0.565    0.6678    0.6676       0.2382       0.2381   0.6931   NaN    1.0652
    h2h_h1    2026      betus (ref)    212   0.585    0.6595    0.6553       0.2338       0.2319   0.6931   NaN    1.0725
    h2h_h1    2026          fanduel    277   0.563    0.6598    0.6582       0.2343       0.2338   0.6931   NaN    1.0601
    h2h_h1    2026     gtbets (ref)    390   0.567    0.6696    0.6680       0.2389       0.2382   0.6931   NaN    1.0703
    h2h_h1    2026 mybookieag (ref)     37   0.514    0.6477    0.6472       0.2289       0.2288   0.6931   NaN    1.0779
    h2h_h1    2027           betmgm    101   0.624    0.6442    0.6405       0.2265       0.2247   0.6931   NaN    1.0905
    h2h_h1    2027        betrivers    102   0.618    0.6420    0.6389       0.2257       0.2243   0.6931   NaN    1.0885
    h2h_h1    2027      betus (ref)     79   0.595    0.6517    0.6467       0.2301       0.2276   0.6931   NaN    1.0742
    h2h_h1    2027          fanduel    103   0.621    0.6406    0.6351       0.2252       0.2226   0.6931   NaN    1.0601
    h2h_h1    2027     gtbets (ref)     93   0.624    0.6412    0.6355       0.2252       0.2226   0.6931   NaN    1.0705
    h2h_h1    2027 mybookieag (ref)     96   0.625    0.6389    0.6324       0.2242       0.2213   0.6931   NaN    1.0500
spreads_q1    2024      betus (ref)    316   0.475    0.6930    0.6931       0.2499       0.2500   0.6931  0.25    1.0874
spreads_q1    2025      betus (ref)    245   0.559    0.6895    0.6909       0.2482       0.2489   0.6931  0.87    1.0897
spreads_q1    2026           betmgm    313   0.505    0.6897    0.6853       0.2483       0.2461   0.6931 -0.40    1.0908
spreads_q1    2026         fanatics     58   0.483    0.6303    0.6915       0.2190       0.2492   0.6931 -0.95    1.0699
spreads_q1    2026          fanduel    313   0.508    0.6920    0.6891       0.2494       0.2480   0.6931 -0.41    1.0606
spreads_q1    2027        betrivers    106   0.594    0.6940    0.6908       0.2504       0.2488   0.6931  2.02    1.0888
spreads_q1    2027          fanduel    107   0.589    0.6956    0.6936       0.2512       0.2502   0.6931  1.81    1.0606
 totals_q1    2024      betus (ref)    317   0.467    0.6935    0.6929       0.2502       0.2499   0.6931 -0.55    1.0872
 totals_q1    2025      betus (ref)    247   0.453    0.6935    0.6931       0.2502       0.2500   0.6931 -0.52    1.0902
 totals_q1    2026           betmgm    222   0.473    0.6905    0.6912       0.2487       0.2491   0.6931  0.03    1.0916
 totals_q1    2026         fanatics     58   0.466    0.6836    0.6915       0.2452       0.2492   0.6931  0.19    1.0704
 totals_q1    2026          fanduel    313   0.482    0.6907    0.6913       0.2488       0.2491   0.6931  0.18    1.0604
 totals_q1    2027        betrivers    106   0.519    0.6927    0.6921       0.2498       0.2495   0.6931  0.75    1.0888
 totals_q1    2027          fanduel    107   0.533    0.6958    0.6958       0.2513       0.2513   0.6931  0.86    1.0711
    h2h_q1    2024      betus (ref)    252   0.548    0.6809    0.6821       0.2439       0.2444   0.6931   NaN    1.0758
    h2h_q1    2025      betus (ref)     85   0.565    0.6600    0.6628       0.2342       0.2355   0.6931   NaN    1.0701
    h2h_q1    2026        betrivers    301   0.558    0.6802    0.6806       0.2436       0.2438   0.6931   NaN    1.0653
    h2h_q1    2027           betmgm    100   0.620    0.6632    0.6668       0.2352       0.2370   0.6931   NaN    1.0917
    h2h_q1    2027        betrivers    102   0.618    0.6670    0.6692       0.2370       0.2381   0.6931   NaN    1.0890

==== (a') pooled over seasons at T-10 (every quote row; calib_slope = slope of result on the de-vigged probability, 1.0 = calibrated) ====
    market          books  quote_rows  games  ll_close  brier  calib_slope
spreads_h1      decidable         916    423    0.6894 0.2482        1.139
spreads_h1 offshore (ref)        1977   1137    0.6928 0.2498        1.799
 totals_h1      decidable         891    423    0.6895 0.2482        1.317
 totals_h1 offshore (ref)        1989   1137    0.6936 0.2502       -2.354
    h2h_h1      decidable        1234    450    0.6600 0.2343        0.877
    h2h_h1 offshore (ref)        1624   1045    0.6522 0.2304        0.980
spreads_q1      decidable         904    423    0.6884 0.2476        1.345
spreads_q1 offshore (ref)         571    571    0.6915 0.2492        6.336
 totals_q1      decidable         806    421    0.6911 0.2490        0.987
 totals_q1 offshore (ref)         574    574    0.6935 0.2502       -2.432
    h2h_q1      decidable         506    404    0.6744 0.2407        0.751
    h2h_q1 offshore (ref)         340    340    0.6739 0.2406        0.920

==== (b) the books' period number and the result, against the full-game anchor at T-10 ====
For spreads the 'result' is minus the home margin (a home number), so both columns are home numbers;
b = slope, a = intercept; ratio = period number / full-game number; resid_sd_line = how far the book's
period number strays from its own straight-line map off the full game.
                         anchor period   kind  season  games  line_on_fg_b  line_on_fg_a  result_on_fg_b  result_on_fg_a  ratio_line  ratio_line_sd  ratio_result  resid_sd_line  mean_res_minus_line
  Pinnacle ladder, every season     h1  total    2024    283        0.4974         0.897          0.5495          -6.962      0.5029         0.0030        0.5068          0.487                0.650
  Pinnacle ladder, every season     h1  total    2025    320        0.4981         0.406          0.5654         -10.961      0.5005         0.0033        0.4996          0.545               -0.144
  Pinnacle ladder, every season     h1  total    2026    402        0.4879         2.481          0.7218         -37.267      0.5024         0.0027        0.5038          0.446                0.285
  Pinnacle ladder, every season     h1  total    2027    107        0.4981         0.671          0.5327          -5.873      0.5019         0.0021        0.4987          0.356               -0.544
  Pinnacle ladder, every season     h1 spread    2024    282        0.5372         0.014          0.4018          -0.565         NaN            NaN           NaN          0.361               -0.108
  Pinnacle ladder, every season     h1 spread    2025    320        0.5279        -0.019          0.5367          -0.183         NaN            NaN           NaN          0.539               -0.192
  Pinnacle ladder, every season     h1 spread    2026    402        0.5186        -0.012          0.4356          -0.072         NaN            NaN           NaN          0.327                0.208
  Pinnacle ladder, every season     h1 spread    2027    107        0.5328        -0.053          0.5482          -1.432         NaN            NaN           NaN          0.313               -1.425
  Pinnacle ladder, every season     q1  total    2024    279        0.2339         3.226          0.1910           9.751      0.2537         0.0031        0.2507          0.494               -0.491
  Pinnacle ladder, every season     q1  total    2025    247        0.2461         0.767          0.2793          -5.295      0.2507         0.0021        0.2475          0.355               -0.524
  Pinnacle ladder, every season     q1  total    2026    324        0.2482         0.527          0.3878         -23.177      0.2513         0.0023        0.2524          0.394                0.225
  Pinnacle ladder, every season     q1  total    2027    107        0.2555        -0.648          0.2714          -2.612      0.2517         0.0016        0.2563          0.280                0.790
  Pinnacle ladder, every season     q1 spread    2024    279        0.2610        -0.043          0.1787          -0.492         NaN            NaN           NaN          0.380               -0.163
  Pinnacle ladder, every season     q1 spread    2025    245        0.2538        -0.039          0.3949          -0.468         NaN            NaN           NaN          0.370               -0.869
  Pinnacle ladder, every season     q1 spread    2026    326        0.2751         0.072          0.1965           0.240         NaN            NaN           NaN          0.398                0.430
  Pinnacle ladder, every season     q1 spread    2027    107        0.2700         0.062          0.3670          -1.517         NaN            NaN           NaN          0.230               -1.874
US five-book consensus, 2025-26     h1  total    2026    402        0.4981         0.707          0.7447         -41.214      0.5023         0.0025        0.5037          0.423                0.285
US five-book consensus, 2025-26     h1 spread    2026    402        0.5088        -0.047          0.4342          -0.080         NaN            NaN           NaN          0.325                0.208
US five-book consensus, 2025-26     q1  total    2026    324        0.2545        -0.569          0.4005         -25.364      0.2512         0.0022        0.2524          0.370                0.225
US five-book consensus, 2025-26     q1 spread    2026    326        0.2695         0.050          0.1960           0.236         NaN            NaN           NaN          0.394                0.430

==== (b') the period line's error by full-game band (Pinnacle ladder fair at T-10, every season pooled) ====
-- h1 total: err = result minus line (over > 0)
            games  mean_err  side_a_rate
band                                    
(0, 155]       20    -1.800        0.389
(155, 160]     99     1.510        0.526
(160, 165]    238    -0.685        0.451
(165, 170]    348    -0.703        0.455
(170, 175]    253     1.418        0.562
(175, 180]    109     0.817        0.537
(180, 999]     45     0.911        0.556
-- h1 spread: err = home margin + home number (home covers > 0)
            games  mean_err  side_a_rate
band                                    
(-99, -12]     45     0.222        0.511
(-12, -8]     152     0.265        0.510
(-8, -4]      360    -0.234        0.506
(-4, 0]       249    -0.262        0.472
(0, 4]        175     1.040        0.589
(4, 8]        113     1.217        0.550
(8, 99]        17    -3.500        0.375
-- q1 total: err = result minus line (over > 0)
            games  mean_err  side_a_rate
band                                    
(0, 155]       20    -0.850        0.500
(155, 160]     88    -0.102        0.523
(160, 165]    211    -0.244        0.460
(165, 170]    290    -0.924        0.443
(170, 175]    213     0.493        0.493
(175, 180]     92     0.826        0.516
(180, 999]     43     1.291        0.525
-- q1 spread: err = home margin + home number (home covers > 0)
            games  mean_err  side_a_rate
band                                    
(-99, -12]     39     0.603        0.513
(-12, -8]     138     0.917        0.544
(-8, -4]      307     0.231        0.508
(-4, 0]       205    -0.309        0.495
(0, 4]        155     0.542        0.516
(4, 8]         97     0.892        0.635
(8, 99]        16    -0.594        0.438
```

## 6. The catalogued method, run unchanged (task 4)

"A half priced from the full-game consensus", in the repo's own pricing code
(imported from `models/ncaab_first_half_spread.py` and
`models/ncaab_first_half_total.py`, not copied): one least-squares map of the
period outcome on the full-game number, the repo's kernel outcome table, every
decidable on-centre quote priced, one bet a game at the largest edge above the
cut, graded at that book's quoted price. Moneylines are priced off the margin
table with a tie pushing. **Two departures, both forced:** the team
half-tendency term is left out (its prior needs last season's full-game lines;
in its source it moved the mean by at most about a quarter point); and the
201-game (V1) and 291-game (V2, first fit) tables never reach the table's
500-game kernel floor, so they are the method's own fallback, every fitting
game shifted to the mean. The 621- and 1,023-game V2 tables reach the floor by
widening the bandwidth to about 1.2-4.5 points at the median key (up to 8.7 in
the tails; `r1_kill2.py`, table 1).

- **V1, the brief's version:** 2025-26 only, anchor = the five-book US
  consensus from the spool at the same snapshot, split at the median tip
  (2026-01-08 19:30Z): 201 games fit, 201 graded.
- **V2, a walk-forward on Pinnacle's ladder:** fit on every earlier season
  (2023-24 -> grade 2024-25; + 2024-25 -> grade 2025-26; + 2025-26 -> grade
  2026-27), graded at the decidable books and, as reference, the offshore ones.

Up to 216 cells (6 markets x 2 reads x 6 cuts, V1 decidable, V2 decidable and
offshore). At the catalogued cut 0.02, T-10:

| Version | Market | Bets | Units | Return [90%] |
|---|---|---|---|---|
| V1 | first-half total | 51 | +17.14 | +29.78% [+8.56, +49.99] |
| V1 | first-half spread | 91 | -13.84 | -13.36% [-29.37, +3.18] |
| V1 | first-half moneyline | 121 | +5.30 | +4.40% [-16.55, +24.35] |
| V1 | first-quarter total | 18 | +5.78 | +30.61% [-2.20, +63.04] |
| V1 | first-quarter spread | 9 | -1.15 | -8.63% |
| V1 | first-quarter moneyline | 15 | +7.93 | +42.63% |
| V2 decidable | first-half total | 37 | -3.24 | -7.80% [-31.21, +17.89] |
| V2 decidable | first-half spread | 65 | -12.72 | -16.88% [-35.77, +1.67] |
| V2 decidable | first-half moneyline | 118 | -26.55 | -19.87% [-34.46, -4.88] |
| V2 decidable | first-quarter total | 59 | +10.85 | +14.96% [-5.49, +32.97] |
| V2 decidable | first-quarter spread | 3 | -1.21 | |
| V2 decidable | first-quarter moneyline | 7 | +2.25 | |

**Does the full-game-to-half mapping look mispriced? No.** The books' map is a
near-constant fraction with half a point of scatter, and a map fitted on
enough games (V2: 621+, slope 0.51-0.59 for the first-half total) agrees with
it so closely that it rarely finds a 2% edge, and loses where it does. V1's
disagreements come from a slope of 0.71 fitted on 201 games of one season.

Printed by `scripts/euroleague_research/r1_method.py`:

```
V1 time split at 2026-01-08 19:30:00+00:00: 201 fitting games, 201 graded
V1 spreads_h1: a = 0.128, b = 0.2946 on 201 games
V2 spreads_h1 grade 2025: a = 0.696, b = 0.4110 on 291 games
V2 spreads_h1 grade 2026: a = 0.452, b = 0.4689 on 621 games
V2 spreads_h1 grade 2027: a = 0.298, b = 0.4576 on 1023 games
V1 totals_h1: a = -35.354, b = 0.7085 on 201 games
V2 totals_h1 grade 2025: a = -5.606, b = 0.5413 on 291 games
V2 totals_h1 grade 2026: a = -1.865, b = 0.5144 on 621 games
V2 totals_h1 grade 2027: a = -13.576, b = 0.5846 on 1023 games
V1 h2h_h1: a = 0.128, b = 0.2946 on 201 games
V2 h2h_h1 grade 2025: a = 0.696, b = 0.4110 on 291 games
V2 h2h_h1 grade 2026: a = 0.452, b = 0.4689 on 621 games
V2 h2h_h1 grade 2027: a = 0.298, b = 0.4576 on 1023 games
V1 spreads_q1: a = -0.162, b = 0.2326 on 201 games
V2 spreads_q1 grade 2025: a = 0.596, b = 0.1912 on 291 games
V2 spreads_q1 grade 2026: a = 0.371, b = 0.2636 on 621 games
V2 spreads_q1 grade 2027: a = 0.183, b = 0.2408 on 1023 games
V1 totals_q1: a = -16.906, b = 0.3508 on 201 games
V2 totals_q1 grade 2025: a = 9.805, b = 0.1912 on 291 games
V2 totals_q1 grade 2026: a = 1.476, b = 0.2412 on 621 games
V2 totals_q1 grade 2027: a = -7.826, b = 0.2978 on 1023 games
V1 h2h_q1: a = -0.162, b = 0.2326 on 201 games
V2 h2h_q1 grade 2025: a = 0.596, b = 0.1912 on 291 games
V2 h2h_q1 grade 2026: a = 0.371, b = 0.2636 on 621 games
V2 h2h_q1 grade 2027: a = 0.183, b = 0.2408 on 1023 games

==== V1: the cut grid, every graded season pooled ====
version     market mark     books  cut seasons  bets  W   L  P  units    ret%     lo%     hi%
     V1     h2h_h1 T-10 decidable 0.00    2026   158 57  98  3  -6.53   -4.07  -18.33    9.49
     V1     h2h_h1 T-10 decidable 0.01    2026   139 51  86  2   1.22    0.88  -16.01   16.67
     V1     h2h_h1 T-10 decidable 0.02    2026   121 45  74  2   5.30    4.40  -16.55   24.35
     V1     h2h_h1 T-10 decidable 0.03    2026   100 39  60  1  11.32   11.40  -10.14   33.92
     V1     h2h_h1 T-10 decidable 0.04    2026    79 27  51  1   1.82    2.33  -24.03   29.51
     V1     h2h_h1 T-10 decidable 0.05    2026    61 21  40  0   2.72    4.46  -21.62   34.17
     V1     h2h_h1 T-60 decidable 0.00    2026   162 59 100  3  -4.82   -2.94  -16.63   10.20
     V1     h2h_h1 T-60 decidable 0.01    2026   137 51  84  2   3.36    2.45  -14.63   18.45
     V1     h2h_h1 T-60 decidable 0.02    2026   121 45  74  2   5.87    4.90  -14.44   24.24
     V1     h2h_h1 T-60 decidable 0.03    2026    95 37  57  1  11.74   12.46  -10.70   33.99
     V1     h2h_h1 T-60 decidable 0.04    2026    78 28  49  1   5.82    7.56  -20.54   36.50
     V1     h2h_h1 T-60 decidable 0.05    2026    63 23  40  0   5.69    9.03  -18.17   38.66
     V1     h2h_q1 T-10 decidable 0.00    2026    65 31  30  4  -5.24   -6.37  -26.47   11.84
     V1     h2h_q1 T-10 decidable 0.01    2026    39 23  14  2   8.30   16.83   -8.05   42.47
     V1     h2h_q1 T-10 decidable 0.02    2026    15 10   4  1   7.93   42.63   -7.35   85.03
     V1     h2h_q1 T-10 decidable 0.03    2026     4  2   1  1   2.46   63.24 -100.00  285.00
     V1     h2h_q1 T-10 decidable 0.04             0  0   0  0   0.00     NaN     NaN     NaN
     V1     h2h_q1 T-10 decidable 0.05             0  0   0  0   0.00     NaN     NaN     NaN
     V1     h2h_q1 T-60 decidable 0.00    2026    64 31  31  2  -6.24   -7.48  -27.37   11.65
     V1     h2h_q1 T-60 decidable 0.01    2026    33 17  15  1   1.05    2.54  -26.12   32.99
     V1     h2h_q1 T-60 decidable 0.02    2026    11  5   5  1   0.28    2.09  -65.30   72.37
     V1     h2h_q1 T-60 decidable 0.03    2026     4  1   3  0  -0.54  -12.30 -100.00  163.10
     V1     h2h_q1 T-60 decidable 0.04             0  0   0  0   0.00     NaN     NaN     NaN
     V1     h2h_q1 T-60 decidable 0.05             0  0   0  0   0.00     NaN     NaN     NaN
     V1 spreads_h1 T-10 decidable 0.00    2026   141 65  76  0 -20.65  -12.92  -23.66   -2.17
     V1 spreads_h1 T-10 decidable 0.01    2026   109 49  60  0 -18.67  -15.13  -29.05   -0.78
     V1 spreads_h1 T-10 decidable 0.02    2026    91 42  49  0 -13.84  -13.36  -29.37    3.18
     V1 spreads_h1 T-10 decidable 0.03    2026    73 36  37  0  -6.04   -7.30  -23.07    8.97
     V1 spreads_h1 T-10 decidable 0.04    2026    53 25  28  0  -6.52  -11.00  -28.52    7.79
     V1 spreads_h1 T-10 decidable 0.05    2026    44 21  23  0  -4.39   -9.01  -30.36   13.94
     V1 spreads_h1 T-60 decidable 0.00    2026   142 66  76  0 -19.13  -11.85  -24.55   -0.46
     V1 spreads_h1 T-60 decidable 0.01    2026   107 49  58  0 -15.93  -13.10  -28.21    2.76
     V1 spreads_h1 T-60 decidable 0.02    2026    92 45  47  0  -7.95   -7.59  -23.75   10.74
     V1 spreads_h1 T-60 decidable 0.03    2026    73 36  37  0  -5.88   -7.10  -25.85   11.60
     V1 spreads_h1 T-60 decidable 0.04    2026    50 23  27  0  -7.47  -13.29  -31.90    7.13
     V1 spreads_h1 T-60 decidable 0.05    2026    44 21  23  0  -4.73   -9.60  -30.07   15.61
     V1 spreads_q1 T-10 decidable 0.00    2026    61 38  23  0  10.20   13.95   -7.94   35.18
     V1 spreads_q1 T-10 decidable 0.01    2026    19 10   9  0  -1.84   -7.34  -43.73   25.10
     V1 spreads_q1 T-10 decidable 0.02    2026     9  5   4  0  -1.15   -8.63  -59.01   40.40
     V1 spreads_q1 T-10 decidable 0.03    2026     7  4   3  0  -0.25   -2.51  -69.59   48.98
     V1 spreads_q1 T-10 decidable 0.04    2026     4  2   2  0  -0.70  -12.39 -100.00   41.43
     V1 spreads_q1 T-10 decidable 0.05    2026     3  1   2  0  -1.70  -39.53 -100.00   20.93
     V1 spreads_q1 T-60 decidable 0.00    2026    55 32  23  0   4.36    6.54  -13.15   26.03
     V1 spreads_q1 T-60 decidable 0.01    2026    22 14   8  0   4.18   15.00  -16.39   45.55
     V1 spreads_q1 T-60 decidable 0.02    2026     9  6   3  0   2.11   17.11  -29.53   68.58
     V1 spreads_q1 T-60 decidable 0.03    2026     5  3   2  0   0.26    3.60  -64.66   64.27
     V1 spreads_q1 T-60 decidable 0.04    2026     3  1   2  0  -1.74  -39.19 -100.00   18.94
     V1 spreads_q1 T-60 decidable 0.05    2026     2  0   2  0  -2.74 -100.00 -100.00 -100.00
     V1  totals_h1 T-10 decidable 0.00    2026    97 60  37  0  18.39   16.64   -0.67   33.03
     V1  totals_h1 T-10 decidable 0.01    2026    71 44  27  0  13.78   17.11   -1.89   36.08
     V1  totals_h1 T-10 decidable 0.02    2026    51 35  16  0  17.14   29.78    8.56   49.99
     V1  totals_h1 T-10 decidable 0.03    2026    34 25   9  0  15.08   39.39   13.56   62.83
     V1  totals_h1 T-10 decidable 0.04    2026    22 17   5  0  11.39   45.61   19.09   70.58
     V1  totals_h1 T-10 decidable 0.05    2026    13 11   2  0   8.79   59.47   26.26   87.13
     V1  totals_h1 T-60 decidable 0.00    2026    98 62  36  0  21.29   19.04    1.81   36.35
     V1  totals_h1 T-60 decidable 0.01    2026    69 45  24  0  18.00   22.96    3.55   40.70
     V1  totals_h1 T-60 decidable 0.02    2026    54 37  17  0  17.71   28.90    7.32   49.38
     V1  totals_h1 T-60 decidable 0.03    2026    33 23  10  0  11.64   31.02    5.98   53.82
     V1  totals_h1 T-60 decidable 0.04    2026    24 18   6  0  11.16   40.79   12.16   65.22
     V1  totals_h1 T-60 decidable 0.05    2026    15 12   3  0   8.66   51.00   16.39   76.95
     V1  totals_q1 T-10 decidable 0.00    2026    69 39  30  0   6.30    8.41  -10.88   26.42
     V1  totals_q1 T-10 decidable 0.01    2026    35 20  15  0   3.78   10.08  -17.53   37.89
     V1  totals_q1 T-10 decidable 0.02    2026    18 12   6  0   5.78   30.61   -2.20   63.04
     V1  totals_q1 T-10 decidable 0.03    2026     5  2   3  0  -1.10  -21.03 -100.00   56.44
     V1  totals_q1 T-10 decidable 0.04    2026     2  1   1  0  -0.08   -3.65 -100.00   90.09
     V1  totals_q1 T-10 decidable 0.05             0  0   0  0   0.00     NaN     NaN     NaN
     V1  totals_q1 T-60 decidable 0.00    2026    55 32  23  0   6.77   11.29   -8.36   31.18
     V1  totals_q1 T-60 decidable 0.01    2026    24 13  11  0   1.17    4.56  -27.92   36.60
     V1  totals_q1 T-60 decidable 0.02    2026    11  7   4  0   2.84   24.55  -28.23   60.73
     V1  totals_q1 T-60 decidable 0.03    2026     3  1   2  0  -1.08  -34.84 -100.00   32.89
     V1  totals_q1 T-60 decidable 0.04    2026     1  0   1  0  -1.08 -100.00 -100.00 -100.00
     V1  totals_q1 T-60 decidable 0.05             0  0   0  0   0.00     NaN     NaN     NaN

==== V2: the cut grid, every graded season pooled ====
version     market mark          books  cut        seasons  bets   W   L  P  units    ret%     lo%     hi%
     V2     h2h_h1 T-10      decidable 0.00      2026,2027   289 122 156 11 -29.13   -8.55  -17.98    0.33
     V2     h2h_h1 T-10      decidable 0.01      2026,2027   190  79 106  5 -15.21   -7.08  -18.24    4.12
     V2     h2h_h1 T-10      decidable 0.02      2026,2027   118  43  74  1 -26.55  -19.87  -34.46   -4.88
     V2     h2h_h1 T-10      decidable 0.03      2026,2027    70  25  45  0 -14.58  -18.58  -39.70    3.13
     V2     h2h_h1 T-10      decidable 0.04      2026,2027    34  13  21  0  -1.18   -3.26  -41.54   33.08
     V2     h2h_h1 T-10      decidable 0.05      2026,2027    15   7   8  0   5.75   37.83  -22.85  105.20
     V2     h2h_h1 T-10 offshore (ref) 0.00 2025,2026,2027   466 229 221 16 -43.29   -6.86  -14.29    0.46
     V2     h2h_h1 T-10 offshore (ref) 0.01 2025,2026,2027   337 166 163  8 -31.51   -6.89  -14.17    0.24
     V2     h2h_h1 T-10 offshore (ref) 0.02 2025,2026,2027   215 105 108  2 -26.13   -8.95  -19.91    0.81
     V2     h2h_h1 T-10 offshore (ref) 0.03 2025,2026,2027   106  49  56  1 -18.15  -13.09  -26.26    0.66
     V2     h2h_h1 T-10 offshore (ref) 0.04 2025,2026,2027    42  28  13  1  13.87   25.74    4.74   45.51
     V2     h2h_h1 T-10 offshore (ref) 0.05 2025,2026,2027     8   3   5  0  -1.80  -19.11  -75.64   41.91
     V2     h2h_h1 T-60      decidable 0.00      2026,2027   287 124 152 11 -23.31   -6.92  -16.40    1.55
     V2     h2h_h1 T-60      decidable 0.01      2026,2027   192  78 108  6 -19.10   -8.83  -21.52    4.54
     V2     h2h_h1 T-60      decidable 0.02      2026,2027   111  38  71  2 -29.56  -23.80  -40.42   -6.62
     V2     h2h_h1 T-60      decidable 0.03      2026,2027    63  21  42  0 -15.98  -22.81  -45.85    0.55
     V2     h2h_h1 T-60      decidable 0.04      2026,2027    26   8  18  0  -3.38  -12.67  -51.69   29.68
     V2     h2h_h1 T-60      decidable 0.05      2026,2027    13   6   7  0   5.20   38.81  -35.67  129.55
     V2     h2h_h1 T-60 offshore (ref) 0.00 2025,2026,2027   468 232 219 17 -37.02   -5.86  -12.76    1.13
     V2     h2h_h1 T-60 offshore (ref) 0.01 2025,2026,2027   329 156 162 11 -42.81   -9.83  -18.44   -1.50
     V2     h2h_h1 T-60 offshore (ref) 0.02 2025,2026,2027   204  96 104  4 -32.11  -11.83  -22.74   -1.84
     V2     h2h_h1 T-60 offshore (ref) 0.03 2025,2026,2027   100  46  52  2 -19.11  -14.62  -29.87    0.22
     V2     h2h_h1 T-60 offshore (ref) 0.04 2025,2026,2027    46  24  21  1  -1.09   -1.82  -24.36   18.71
     V2     h2h_h1 T-60 offshore (ref) 0.05      2025,2027    10   6   4  0   1.49   11.46  -37.55   46.77
     V2     h2h_q1 T-10      decidable 0.00           2026    38  15  19  4   6.06   17.71   -9.76   47.89
     V2     h2h_q1 T-10      decidable 0.01           2026    14   8   5  1   9.83   75.62   15.37  139.01
     V2     h2h_q1 T-10      decidable 0.02           2026     7   3   4  0   2.25   32.14  -61.43  125.71
     V2     h2h_q1 T-10      decidable 0.03           2026     3   1   2  0  -0.30  -10.00 -100.00   80.00
     V2     h2h_q1 T-10      decidable 0.04                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-10      decidable 0.05                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-10 offshore (ref) 0.00           2025    12   4   8  0  -2.80  -22.58  -70.14   30.94
     V2     h2h_q1 T-10 offshore (ref) 0.01           2025     2   1   1  0  -0.00   -0.00 -100.00   86.96
     V2     h2h_q1 T-10 offshore (ref) 0.02                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-10 offshore (ref) 0.03                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-10 offshore (ref) 0.04                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-10 offshore (ref) 0.05                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60      decidable 0.00           2026    36  14  18  4   6.05   18.86   -8.91   50.88
     V2     h2h_q1 T-60      decidable 0.01           2026    16   8   7  1   7.51   50.07   -6.51  108.28
     V2     h2h_q1 T-60      decidable 0.02           2026     5   3   2  0   4.10   82.00  -46.00  187.15
     V2     h2h_q1 T-60      decidable 0.03           2026     2   0   2  0  -2.00 -100.00 -100.00 -100.00
     V2     h2h_q1 T-60      decidable 0.04                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60      decidable 0.05                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60 offshore (ref) 0.00           2025    12   4   8  0  -2.80  -22.58  -69.95   30.07
     V2     h2h_q1 T-60 offshore (ref) 0.01           2025     3   2   1  0   1.45   46.03  -31.75  123.81
     V2     h2h_q1 T-60 offshore (ref) 0.02                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60 offshore (ref) 0.03                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60 offshore (ref) 0.04                    0   0   0  0   0.00     NaN     NaN     NaN
     V2     h2h_q1 T-60 offshore (ref) 0.05                    0   0   0  0   0.00     NaN     NaN     NaN
     V2 spreads_h1 T-10      decidable 0.00      2026,2027   215 102 113  0 -27.83  -11.28  -21.75   -0.99
     V2 spreads_h1 T-10      decidable 0.01      2026,2027   129  56  73  0 -28.27  -18.98  -31.55   -5.85
     V2 spreads_h1 T-10      decidable 0.02      2026,2027    65  29  36  0 -12.72  -16.88  -35.77    1.67
     V2 spreads_h1 T-10      decidable 0.03      2026,2027    29  14  15  0  -4.12  -11.91  -39.90   16.64
     V2 spreads_h1 T-10      decidable 0.04      2026,2027    13   8   5  0   1.90   11.94  -30.70   55.34
     V2 spreads_h1 T-10      decidable 0.05           2026     5   3   2  0   0.82   14.26  -53.59   84.75
     V2 spreads_h1 T-10 offshore (ref) 0.00 2025,2026,2027   429 225 196  8  -1.96   -0.40   -8.19    6.92
     V2 spreads_h1 T-10 offshore (ref) 0.01 2025,2026,2027   296 152 139  5  -8.66   -2.57  -11.87    5.91
     V2 spreads_h1 T-10 offshore (ref) 0.02 2025,2026,2027   177  90  84  3  -6.94   -3.44  -14.51    8.05
     V2 spreads_h1 T-10 offshore (ref) 0.03 2025,2026,2027   114  56  55  3  -7.26   -5.63  -19.80    9.63
     V2 spreads_h1 T-10 offshore (ref) 0.04 2025,2026,2027    60  31  27  2  -0.26   -0.38  -19.84   19.65
     V2 spreads_h1 T-10 offshore (ref) 0.05 2025,2026,2027    39  19  18  2  -1.87   -4.30  -28.73   20.59
     V2 spreads_h1 T-60      decidable 0.00      2026,2027   212 103 109  0 -21.19   -8.69  -18.85    1.96
     V2 spreads_h1 T-60      decidable 0.01      2026,2027   119  54  65  0 -19.91  -14.52  -28.03   -0.77
     V2 spreads_h1 T-60      decidable 0.02      2026,2027    60  24  36  0 -16.88  -24.31  -42.52   -5.91
     V2 spreads_h1 T-60      decidable 0.03      2026,2027    20  11   9  0   0.07    0.29  -34.02   33.91
     V2 spreads_h1 T-60      decidable 0.04           2026     9   7   2  0   4.63   42.24    1.76   81.30
     V2 spreads_h1 T-60      decidable 0.05           2026     5   4   1  0   2.85   46.34   10.77   82.64
     V2 spreads_h1 T-60 offshore (ref) 0.00 2025,2026,2027   411 220 186  5   5.19    1.10   -6.43    8.08
     V2 spreads_h1 T-60 offshore (ref) 0.01 2025,2026,2027   280 149 127  4   2.72    0.85   -8.69    9.76
     V2 spreads_h1 T-60 offshore (ref) 0.02 2025,2026,2027   169  92  74  3   6.68    3.47   -9.22   16.00
     V2 spreads_h1 T-60 offshore (ref) 0.03 2025,2026,2027   102  52  48  2  -3.21   -2.75  -19.51   12.60
     V2 spreads_h1 T-60 offshore (ref) 0.04 2025,2026,2027    61  34  26  1   3.80    5.36  -15.38   25.15
     V2 spreads_h1 T-60 offshore (ref) 0.05      2025,2026    36  21  14  1   4.73   11.35  -16.08   36.21
     V2 spreads_q1 T-10      decidable 0.00      2026,2027    34  14  20  0  -8.16  -21.23  -48.73    7.15
     V2 spreads_q1 T-10      decidable 0.01      2026,2027    11   5   6  0  -1.58  -13.17  -65.05   38.31
     V2 spreads_q1 T-10      decidable 0.02      2026,2027     3   1   2  0  -1.21  -37.69 -100.00   29.03
     V2 spreads_q1 T-10      decidable 0.03           2026     1   0   1  0  -1.10 -100.00 -100.00 -100.00
     V2 spreads_q1 T-10      decidable 0.04           2026     1   0   1  0  -1.10 -100.00 -100.00 -100.00
     V2 spreads_q1 T-10      decidable 0.05           2026     1   0   1  0  -1.10 -100.00 -100.00 -100.00
     V2 spreads_q1 T-10 offshore (ref) 0.00      2025,2026    63  34  29  0  -0.60   -0.79  -22.14   20.98
     V2 spreads_q1 T-10 offshore (ref) 0.01           2025    40  23  17  0   2.85    5.94  -20.50   30.79
     V2 spreads_q1 T-10 offshore (ref) 0.02           2025    23  11  12  0  -3.20  -11.62  -44.04   22.85
     V2 spreads_q1 T-10 offshore (ref) 0.03           2025    16   8   8  0  -1.40   -7.41  -42.25   28.19
     V2 spreads_q1 T-10 offshore (ref) 0.04           2025     9   3   6  0  -4.15  -38.60  -79.72    2.80
     V2 spreads_q1 T-10 offshore (ref) 0.05           2025     3   1   2  0  -1.45  -39.73 -100.00   22.22
     V2 spreads_q1 T-60      decidable 0.00      2026,2027    26   8  18  0 -11.54  -40.46  -70.64  -10.87
     V2 spreads_q1 T-60      decidable 0.01      2026,2027     8   3   5  0  -2.32  -26.91  -75.71   22.22
     V2 spreads_q1 T-60      decidable 0.02      2026,2027     3   0   3  0  -3.22 -100.00 -100.00 -100.00
     V2 spreads_q1 T-60      decidable 0.03      2026,2027     2   0   2  0  -2.22 -100.00 -100.00 -100.00
     V2 spreads_q1 T-60      decidable 0.04           2026     1   0   1  0  -1.14 -100.00 -100.00 -100.00
     V2 spreads_q1 T-60      decidable 0.05           2026     1   0   1  0  -1.14 -100.00 -100.00 -100.00
     V2 spreads_q1 T-60 offshore (ref) 0.00      2025,2026    61  31  30  0  -4.50   -6.18  -28.76   14.36
     V2 spreads_q1 T-60 offshore (ref) 0.01           2025    40  21  19  0  -1.45   -3.03  -28.45   21.67
     V2 spreads_q1 T-60 offshore (ref) 0.02           2025    25  12  13  0  -3.35  -11.19  -40.76   17.93
     V2 spreads_q1 T-60 offshore (ref) 0.03           2025    15   9   6  0   2.00   11.27  -25.29   48.72
     V2 spreads_q1 T-60 offshore (ref) 0.04           2025     9   4   5  0  -1.90  -17.76  -58.69   23.36
     V2 spreads_q1 T-60 offshore (ref) 0.05           2025     3   1   2  0  -1.40  -38.89 -100.00   -8.33
     V2  totals_h1 T-10      decidable 0.00      2026,2027   140  74  66  0  -2.50   -1.52  -12.96   10.17
     V2  totals_h1 T-10      decidable 0.01      2026,2027    79  40  39  0  -4.02   -4.47  -20.86   12.43
     V2  totals_h1 T-10      decidable 0.02      2026,2027    37  18  19  0  -3.24   -7.80  -31.21   17.89
     V2  totals_h1 T-10      decidable 0.03      2026,2027    10   5   5  0  -0.48   -4.38  -58.48   41.56
     V2  totals_h1 T-10      decidable 0.04      2026,2027     4   1   3  0  -2.35  -52.22 -100.00   -1.83
     V2  totals_h1 T-10      decidable 0.05           2026     2   0   2  0  -2.24 -100.00 -100.00 -100.00
     V2  totals_h1 T-10 offshore (ref) 0.00 2025,2026,2027   371 201 169  1   5.73    1.34   -6.64    9.00
     V2  totals_h1 T-10 offshore (ref) 0.01 2025,2026,2027   245 134 110  1   7.62    2.72   -7.16   12.73
     V2  totals_h1 T-10 offshore (ref) 0.02 2025,2026,2027   149  77  71  1  -4.61   -2.71  -14.42    8.94
     V2  totals_h1 T-10 offshore (ref) 0.03 2025,2026,2027    76  39  37  0  -3.66   -4.20  -21.68   13.01
     V2  totals_h1 T-10 offshore (ref) 0.04 2025,2026,2027    36  14  22  0 -11.27  -27.25  -49.35   -1.13
     V2  totals_h1 T-10 offshore (ref) 0.05      2025,2026    11   4   7  0  -3.99  -31.22  -81.79    2.72
     V2  totals_h1 T-60      decidable 0.00      2026,2027   125  67  58  0   0.88    0.61  -10.42   12.36
     V2  totals_h1 T-60      decidable 0.01      2026,2027    73  40  33  0   2.62    3.11  -13.15   19.19
     V2  totals_h1 T-60      decidable 0.02      2026,2027    36  18  18  0  -2.18   -5.40  -27.46   17.44
     V2  totals_h1 T-60      decidable 0.03      2026,2027    10   7   3  0   3.74   34.00   -3.27   70.58
     V2  totals_h1 T-60      decidable 0.04      2026,2027     5   3   2  0   0.92   16.76  -59.51   87.11
     V2  totals_h1 T-60      decidable 0.05      2026,2027     2   0   2  0  -2.08 -100.00 -100.00 -100.00
     V2  totals_h1 T-60 offshore (ref) 0.00 2025,2026,2027   368 201 164  3  11.36    2.69   -4.63   10.42
     V2  totals_h1 T-60 offshore (ref) 0.01 2025,2026,2027   244 128 114  2  -3.37   -1.21  -10.66    8.33
     V2  totals_h1 T-60 offshore (ref) 0.02 2025,2026,2027   134  63  70  1 -17.59  -11.46  -25.26    1.16
     V2  totals_h1 T-60 offshore (ref) 0.03 2025,2026,2027    70  32  38  0 -11.93  -14.69  -31.07    1.80
     V2  totals_h1 T-60 offshore (ref) 0.04 2025,2026,2027    36  14  22  0 -11.36  -27.18  -51.82    0.91
     V2  totals_h1 T-60 offshore (ref) 0.05 2025,2026,2027    13   5   8  0  -4.02  -26.36  -82.98   15.34
     V2  totals_q1 T-10      decidable 0.00      2026,2027   242 134 108  0   7.23    2.49   -7.11   11.85
     V2  totals_q1 T-10      decidable 0.01      2026,2027   123  74  49  0  15.97   10.62   -1.47   23.31
     V2  totals_q1 T-10      decidable 0.02      2026,2027    59  37  22  0  10.85   14.96   -5.49   32.97
     V2  totals_q1 T-10      decidable 0.03      2026,2027    19  13   6  0   6.07   26.38   -3.49   54.62
     V2  totals_q1 T-10      decidable 0.04           2026     6   4   2  0   1.37   17.17  -42.16   72.65
     V2  totals_q1 T-10      decidable 0.05           2026     2   1   1  0  -0.13   -5.63 -100.00   84.75
     V2  totals_q1 T-10 offshore (ref) 0.00      2025,2026    36  19  17  0  -1.55   -3.57  -32.85   23.07
     V2  totals_q1 T-10 offshore (ref) 0.01      2025,2026    21   9  12  0  -5.45  -21.67  -56.18   13.52
     V2  totals_q1 T-10 offshore (ref) 0.02      2025,2026    13   6   7  0  -2.45  -15.76  -58.01   27.10
     V2  totals_q1 T-10 offshore (ref) 0.03      2025,2026    10   4   6  0  -3.25  -27.20  -64.20   28.03
     V2  totals_q1 T-10 offshore (ref) 0.04      2025,2026     5   2   3  0  -1.65  -27.27 -100.00   46.67
     V2  totals_q1 T-10 offshore (ref) 0.05      2025,2026     3   1   2  0  -1.45  -39.73 -100.00   22.22
     V2  totals_q1 T-60      decidable 0.00      2026,2027   206 115  91  0   5.58    2.21   -7.00   11.07
     V2  totals_q1 T-60      decidable 0.01      2026,2027   104  64  40  0  15.20   11.71    0.22   24.30
     V2  totals_q1 T-60      decidable 0.02      2026,2027    52  36  16  0  17.01   26.04    7.79   42.76
     V2  totals_q1 T-60      decidable 0.03      2026,2027    19  14   5  0   8.03   32.96    4.77   58.91
     V2  totals_q1 T-60      decidable 0.04      2026,2027     6   4   2  0   1.53   19.39  -39.86   74.72
     V2  totals_q1 T-60      decidable 0.05           2026     2   1   1  0  -0.13   -5.63 -100.00   84.75
     V2  totals_q1 T-60 offshore (ref) 0.00      2025,2026    32  12  20  0 -12.20  -31.52  -60.13   -3.28
     V2  totals_q1 T-60 offshore (ref) 0.01      2025,2026    17   6  11  0  -7.25  -35.37  -69.59    3.11
     V2  totals_q1 T-60 offshore (ref) 0.02      2025,2026    13   5   8  0  -4.65  -29.62  -71.79   13.10
     V2  totals_q1 T-60 offshore (ref) 0.03      2025,2026     9   2   7  0  -6.45  -59.45 -100.00  -18.14
     V2  totals_q1 T-60 offshore (ref) 0.04      2025,2026     5   2   3  0  -1.65  -27.27 -100.00   46.67
     V2  totals_q1 T-60 offshore (ref) 0.05           2025     2   1   1  0  -0.25  -10.20 -100.00   83.33

==== V2 by graded season, cut 0.02 (the catalogued cut), T-10 ====
    market          books  season  bets  W  L  P  units    ret%     lo%     hi%
    h2h_h1      decidable    2026   110 40 69  1 -25.39  -20.23  -34.44   -4.94
    h2h_h1      decidable    2027     8  3  5  0  -1.16  -14.27  -70.13   40.92
    h2h_h1 offshore (ref)    2025   138 74 62  2  -4.39   -2.23  -14.88   10.14
    h2h_h1 offshore (ref)    2026    66 26 40  0 -22.08  -26.26  -43.64   -9.86
    h2h_h1 offshore (ref)    2027    11  5  6  0   0.34    3.01  -49.01   51.20
    h2h_q1      decidable    2026     7  3  4  0   2.25   32.14  -61.43  125.71
    h2h_q1      decidable    2027     0  0  0  0   0.00     NaN     NaN     NaN
    h2h_q1 offshore (ref)    2025     0  0  0  0   0.00     NaN     NaN     NaN
    h2h_q1 offshore (ref)    2026     0  0  0  0   0.00     NaN     NaN     NaN
spreads_h1      decidable    2026    58 24 34  0 -15.41  -22.80  -43.18   -3.67
spreads_h1      decidable    2027     7  5  2  0   2.69   34.62  -20.80   91.99
spreads_h1 offshore (ref)    2025    93 50 40  3   3.32    3.15  -12.07   17.90
spreads_h1 offshore (ref)    2026    70 31 39  0 -13.26  -16.59  -34.31    0.90
spreads_h1 offshore (ref)    2027    14  9  5  0   3.00   18.53  -15.10   58.15
spreads_q1      decidable    2026     1  0  1  0  -1.10 -100.00 -100.00 -100.00
spreads_q1      decidable    2027     2  1  1  0  -0.11   -5.21 -100.00  100.00
spreads_q1 offshore (ref)    2025    23 11 12  0  -3.20  -11.62  -44.04   22.85
spreads_q1 offshore (ref)    2026     0  0  0  0   0.00     NaN     NaN     NaN
 totals_h1      decidable    2026    16  8  8  0  -0.86   -4.83  -49.24   38.66
 totals_h1      decidable    2027    21 10 11  0  -2.38  -10.03  -32.30   15.92
 totals_h1 offshore (ref)    2025    77 40 36  1  -1.90   -2.16  -16.21   13.58
 totals_h1 offshore (ref)    2026    47 24 23  0  -2.30   -4.30  -26.53   19.85
 totals_h1 offshore (ref)    2027    25 13 12  0  -0.41   -1.45  -28.46   25.71
 totals_q1      decidable    2026    55 34 21  0   9.05   13.34   -7.97   33.50
 totals_q1      decidable    2027     4  3  1  0   1.80   38.63   -8.77   88.50
 totals_q1 offshore (ref)    2025    12  6  6  0  -1.25   -8.71  -54.48   37.81
 totals_q1 offshore (ref)    2026     1  0  1  0  -1.20 -100.00 -100.00 -100.00

==== side split and price at cut 0.02, T-10 ====
version     market          books  bets  side_home  side_away  side_over  side_under  median_price  shortest  share_lt_-200  share_lt_-300  median_edge  distinct_mu                                 books_named
     V1     h2h_h1      decidable   121         55         66          0           0         190.0    -118.0          0.000            0.0       0.0503           28            betrivers:97,fanduel:23,betmgm:1
     V1     h2h_q1      decidable    15         14          1          0           0        -134.0    -165.0          0.000            0.0       0.0244            8                                betrivers:15
     V1 spreads_h1      decidable    91         51         40          0           0        -113.0    -130.0          0.000            0.0       0.0497           24            fanduel:71,betmgm:17,betrivers:3
     V1 spreads_q1      decidable     9          9          0          0           0        -155.0    -190.0          0.000            0.0       0.0380            6                        betmgm:7,betrivers:2
     V1  totals_h1      decidable    51          0          0         37          14        -113.0    -140.0          0.000            0.0       0.0358           24                        fanduel:37,betmgm:14
     V1  totals_q1      decidable    18          0          0          5          13        -104.0    -113.0          0.000            0.0       0.0275           11                                  fanduel:18
     V2     h2h_h1      decidable   118        104         14          0           0         100.0    -160.0          0.000            0.0       0.0331          110            betrivers:75,fanduel:38,betmgm:5
     V2     h2h_h1 offshore (ref)   215        213          2          0           0        -130.0    -235.0          0.037            0.0       0.0298          193            gtbets:128,betus:80,mybookieag:7
     V2     h2h_q1      decidable     7          5          2          0           0         188.0     160.0          0.000            0.0       0.0291            7                                 betrivers:7
     V2 spreads_h1      decidable    65         62          3          0           0        -113.0    -155.0          0.000            0.0       0.0290           58  fanduel:52,betmgm:8,betrivers:4,fanatics:1
     V2 spreads_h1 offshore (ref)   177        156         21          0           0        -115.0    -144.0          0.000            0.0       0.0336          169            betus:102,gtbets:73,mybookieag:2
     V2 spreads_q1      decidable     3          2          1          0           0        -110.0    -111.0          0.000            0.0       0.0287            3                       fanduel:2,betrivers:1
     V2 spreads_q1 offshore (ref)    23          7         16          0           0        -120.0    -145.0          0.000            0.0       0.0337           23                                    betus:23
     V2  totals_h1      decidable    37          0          0         16          21        -113.0    -125.0          0.000            0.0       0.0270           37                      fanduel:32,betrivers:5
     V2  totals_h1 offshore (ref)   149          0          0         98          51        -115.0    -132.0          0.000            0.0       0.0303          140                          gtbets:82,betus:67
     V2  totals_q1      decidable    59          0          0          2          57        -118.0    -190.0          0.000            0.0       0.0262           56 fanduel:38,betmgm:13,fanatics:5,betrivers:3
     V2  totals_q1 offshore (ref)    13          0          0          0          13        -120.0    -125.0          0.000            0.0       0.0352           11                                    betus:13
```

## 7. Kill tests on every positive result

`r1_kill.py` runs the method's own decide/grade code for each test.

**P1. V1 first-half total** (51 bets, +17.14 units, +29.78% [+8.56, +49.99]).
Passed: neighbourhood of cuts (every cut 0.00-0.05 positive); early/late (+14.2%
on 25 bets, +44.5% on 26); every other read T-360 to T-30 positive (+23.5% to
+37.2%); placebo with the anchor shuffled across the graded games (real +29.8%,
200 shuffles' 95th percentile -0.3%); price range (median -113, shortest -140,
none shorter than -200). Failed: **fit on every season available** (822 games:
the slope falls to 0.544 and only 9 bets remain); **the frozen fit read on
unseen seasons** (2026-27 to date -15.1% on 38 bets; 2023-24 at offshore books
-9.6% on 127; 2024-25 +10.8% on 96); **without its 10 best dates** (+2.9% on
35 bets); side split borderline (37 overs of 51, 73%; the blind over on the
same games -0.8%); bets far below the 200-bet bar. Return does not rise
steadily with edge (bands +15.4, -14.6, +10.7, +26.8, +59.5). Verdict: a
2025-26-only slope. Dead as a rule.

**P2. V2 first-quarter total** (59 bets, +10.85 units, +14.96% [-5.49,
+32.97]). Passed: it is walk-forward by construction; neighbourhood at T-10
(+2.5, +10.6, +15.0, +26.4% at cuts 0.00-0.03); early/late (+16.5% / +13.3%);
every other read in 2025-26 positive (+22.0% to +26.8% at T-360 to T-30);
placebo (real +13.3% vs 95th percentile -0.5%); return rises with edge (bands
-6.3, +6.6, +9.7, +30.0%); price range (median -118, shortest -190). Failed:
**side split** (57 of 59 bets are unders; the blind under at the best decidable
price on the same seasons lost -5.4% on 421); **without its 10 best dates**
(-13.1% on 38); **one season carries it** (2025-26: 55 bets, +13.3%; 2026-27: 4
bets; 2024-25 at offshore books: 12 bets, -8.7%); interval includes zero.
**Passed the market-alone control row** (`r1_kill2.py`): the same table, cut,
books and seasons with the market's own median number in place of the
full-game anchor loses at every cut (-8.1% on 14 bets at 0.02, -1.9% on 61 at
0.01, -4.5% on 151 at 0.00), so the anchor, not plain line shopping, carries
the lead. Its mechanism is a fitted first-quarter mean about 0.2-0.3 points
under the books' 25.1% (fit a = 1.476, b = 0.2412 on 2023-24 and 2024-25), so
it buys unders; of its 52 bets on games with 2+ decidable books quoting, 44
sit at the highest decidable number (28 strictly above the lowest). Verdict: a
lead, not a pass (section 10).

Printed by `scripts/euroleague_research/r1_kill2.py`:

```
==== (1) bandwidth the kernel table reaches (start 0.75, x1.25 to 500 games or past 20) ====
h_at_pX = bandwidth reached at the key's X-th percentile; '>20 (n)' = the floor was never met, n = weight reached
    market version                 fit  games  key_sd   h_at_p5  h_at_p50  h_at_p95
 totals_h1      V1  2025-26 first half    201    4.06 >20 (190) >20 (197) >20 (187)
 totals_h1      V2 seasons before 2025    291    2.69 >20 (283) >20 (289) >20 (282)
 totals_h1      V2 seasons before 2026    621    2.78      8.73      4.47      8.73
 totals_h1      V2 seasons before 2027   1023    3.66      5.59      2.29      5.59
spreads_h1      V1  2025-26 first half    201    1.48 >20 (199) >20 (201) >20 (200)
spreads_h1      V2 seasons before 2025    291    2.29 >20 (284) >20 (289) >20 (286)
spreads_h1      V2 seasons before 2026    621    2.62      8.73      4.47      6.98
spreads_h1      V2 seasons before 2027   1023    2.48      4.47      1.46      3.58
 totals_q1      V1  2025-26 first half    201    2.01 >20 (198) >20 (200) >20 (197)
 totals_q1      V2 seasons before 2025    291    0.95 >20 (290) >20 (291) >20 (290)
 totals_q1      V2 seasons before 2026    621    1.30      4.47      1.83      3.58
 totals_q1      V2 seasons before 2027   1023    1.86      2.86      1.17      2.86
spreads_q1      V1  2025-26 first half    201    1.17 >20 (200) >20 (201) >20 (200)
spreads_q1      V2 seasons before 2025    291    1.06 >20 (290) >20 (291) >20 (290)
spreads_q1      V2 seasons before 2026    621    1.47      4.47      2.29      4.47
spreads_q1      V2 seasons before 2027   1023    1.30      2.29      0.75      1.83

==== (2) and (3): V2 first-quarter total, decidable books, T-10 ====
(2) P2 bets at cut 0.02: 59; on games with 2+ decidable books quoting: 52; of those at the highest decidable number: 44 (strictly above the lowest: 28); at the lowest: 22; one decidable book only: 7
    P2 bets by under/over and whether at the highest number: {('over', False): 1, ('over', True): 1, ('under', False): 7, ('under', True): 50}

(3) control row (mu = the market's own median number) against P2 (mu from the full-game anchor):
 cut                         rule  bets   W   L  P  units   ret%     lo%   hi%  unders
0.00         P2: full-game anchor   242 134 108  0   7.23   2.49   -7.11 11.85     236
0.00 control: market's own number   151  76  75  0  -7.60  -4.48  -17.66  8.40     147
0.01         P2: full-game anchor   123  74  49  0  15.97  10.62   -1.47 23.31     121
0.01 control: market's own number    61  32  29  0  -1.30  -1.87  -22.39 19.28      59
0.02         P2: full-game anchor    59  37  22  0  10.85  14.96   -5.49 32.97      57
0.02 control: market's own number    14   7   7  0  -1.32  -8.14  -44.88 31.58      13
0.03         P2: full-game anchor    19  13   6  0   6.07  26.38   -3.49 54.62      18
0.03 control: market's own number     9   4   5  0  -2.09 -19.61  -62.04 25.42       9
0.04         P2: full-game anchor     6   4   2  0   1.37  17.17  -42.16 72.65       6
0.04 control: market's own number     9   4   5  0  -2.09 -19.61  -62.04 25.42       9
0.05         P2: full-game anchor     2   1   1  0  -0.13  -5.63 -100.00 84.75       2
0.05 control: market's own number     4   2   2  0  -0.23  -5.18 -100.00 89.49       4
   control, season 2026, cut 0.02: {'bets': 12, 'W': 6, 'L': 6, 'P': 0, 'units': -1.2, 'ret%': -8.57, 'lo%': np.float64(-54.62), 'hi%': np.float64(40.62)}
   control, season 2027, cut 0.02: {'bets': 2, 'W': 1, 'L': 1, 'P': 0, 'units': -0.12, 'ret%': -5.43, 'lo%': np.float64(-5.43), 'hi%': np.float64(-5.43)}
```

**P3. V1 first-half moneyline** (121 bets, +4.40%). Failed the placebo (84.5th
percentile; 95th +7.2%), early/late (+22.5% / -13.9%), the 10 best dates
(-27.5% without them), fit on every season (-17.7% on 71), the frozen fit on
unseen seasons (2023-24 -18.6% on 60, 2024-25 -10.8% on 115, 2026-27 +2.5% on
50), and its walk-forward twin V2 (-19.9% on 118). Dead.

**P5. V1 first-quarter total** (18 bets, +30.6%). Under 25 bets; failed the
neighbourhood (cuts 0.03 and 0.04 negative), the 10 best dates (-50.3%), the
frozen fit on 2023-24 (-4.4% on 127) and 2024-25 (-26.9% on 15). Dead.

**P4. The blind first-half moneyline underdog** at the best decidable price
(465 bets, +19.14 units, +4.22% [-4.64, +12.35]). Passed early/late inside
2025-26 (+8.1% / +8.6%). Failed the season split (2025-26 +8.4% on 358;
2026-27 -9.8% on 107; offshore earlier seasons: 2023-24 BetUS -17.8% on 256,
2024-25 GTbets -4.2% on 282) and the 10 best dates (-5.9% without them). It is
one side: home underdogs +15.8% on 134 [-1.0, +32.4], away underdogs -0.4% on
331, and the profit sits at +150 to +300 (prices past +300 went 0-18). Dead as
a blind rule; "the home underdog in the first half" is a hypothesis
(section 10).

Printed by `scripts/euroleague_research/r1_kill.py`:

```

==== totals_h1: V1 (2025-26 time split, US consensus anchor), decidable books ====
  frozen fit: a = -35.354, b = 0.7085 on 201 games
  as run (T-10, cut 0.02)                                        bets=51 W=35 L=16 P=0 units=17.14 ret%=29.78 lo%=8.56 hi%=49.99
  side split: {'over': 37, 'under': 14}; prices median -113, shortest -140; books {'fanduel': 37, 'betmgm': 14}
  blind over at the best decidable price, same graded games      bets=201 W=108 L=93 P=0 units=-1.92 ret%=-0.81 lo%=-11.89 hi%=10.03
  early half of the bets (by date)                               bets=25 W=15 L=10 P=0 units=3.98 ret%=14.22 lo%=-18.49 hi%=46.56
  late half of the bets (by date)                                bets=26 W=20 L=6 P=0 units=13.16 ret%=44.52 lo%=17.24 hi%=67.61
  without the 10 best dates                                      bets=35 W=19 L=16 P=0 units=1.14 ret%=2.91 lo%=-20.3 hi%=26.34
  edge band (0.0, 0.01]                                          bets=26 W=16 L=10 P=0 units=4.61 ret%=15.38 lo%=-11.17 hi%=44.28
  edge band (0.01, 0.02]                                         bets=20 W=9 L=11 P=0 units=-3.36 ret%=-14.62 lo%=-50.27 hi%=16.39
  edge band (0.02, 0.03]                                         bets=17 W=10 L=7 P=0 units=2.06 ret%=10.69 lo%=-23.07 hi%=41.79
  edge band (0.03, 0.05]                                         bets=21 W=14 L=7 P=0 units=6.29 ret%=26.77 lo%=-4.28 hi%=58.54
  edge band (0.05, 1.0]                                          bets=13 W=11 L=2 P=0 units=8.79 ret%=59.47 lo%=26.26 hi%=87.13
  read at T-360                                                  bets=45 W=31 L=14 P=0 units=15.23 ret%=29.47 lo%=6.31 hi%=52.32
  read at T-180                                                  bets=44 W=32 L=12 P=0 units=18.54 ret%=37.15 lo%=15.15 hi%=58.54
  read at T-120                                                  bets=50 W=33 L=17 P=0 units=13.84 ret%=24.39 lo%=3.77 hi%=45.03
  read at T-60                                                   bets=54 W=37 L=17 P=0 units=17.71 ret%=28.9 lo%=7.32 hi%=49.38
  read at T-30                                                   bets=53 W=35 L=18 P=0 units=14.29 ret%=23.54 lo%=4.19 hi%=42.59
  read at T-10                                                   bets=51 W=35 L=16 P=0 units=17.14 ret%=29.78 lo%=8.56 hi%=49.99
  fit on every season available (Pinnacle anchor, 822 games): a = -6.921, b = 0.5442
    -> graded on the same second half of 2025-26                 bets=9 W=6 L=3 P=0 units=2.7 ret%=26.76 lo%=-24.06 hi%=68.87
  frozen V1 fit, Pinnacle anchor, same second half (anchor check) bets=55 W=39 L=16 P=0 units=21.33 ret%=34.42 lo%=15.01 hi%=52.59
  frozen V1 fit on 2026-27 to date, decidable books              bets=38 W=18 L=20 P=0 units=-7.03 ret%=-15.1 lo%=-35.49 hi%=2.91
  frozen V1 fit on 2023-24, offshore books (reference)           bets=127 W=60 L=62 P=5 units=-13.94 ret%=-9.58 lo%=-23.71 hi%=4.12
  frozen V1 fit on 2024-25, offshore books (reference)           bets=96 W=56 L=38 P=2 units=11.75 ret%=10.76 lo%=-6.31 hi%=27.94
  placebo (anchor shuffled across graded games, 200x): mean -11.18%, p95 -0.26%, real +29.78% sits at percentile 100.0

==== totals_q1: V2 (walk-forward, Pinnacle-ladder anchor) ====
  season 2026, decidable                                         bets=55 W=34 L=21 P=0 units=9.05 ret%=13.34 lo%=-7.97 hi%=33.5
  season 2027, decidable                                         bets=4 W=3 L=1 P=0 units=1.8 ret%=38.63 lo%=-8.77 hi%=88.5
  pooled 2025-26 + 2026-27 to date, decidable                    bets=59 W=37 L=22 P=0 units=10.85 ret%=14.96 lo%=-5.49 hi%=32.97
  side split: {'under': 57, 'over': 2}; prices median -118, shortest -190; books {'fanduel': 38, 'betmgm': 13, 'fanatics': 5, 'betrivers': 3}
  blind under at the best decidable price, 2025-26 + 2026-27 games bets=421 W=210 L=211 P=0 units=-25.22 ret%=-5.36 lo%=-11.88 hi%=1.27
  early half of the bets (by date)                               bets=29 W=19 L=10 P=0 units=6.2 ret%=16.47 lo%=-11.66 hi%=42.61
  late half of the bets (by date)                                bets=30 W=18 L=12 P=0 units=4.65 ret%=13.34 lo%=-18.38 hi%=39.99
  without the 10 best dates                                      bets=38 W=18 L=20 P=0 units=-5.98 ret%=-13.11 lo%=-38.46 hi%=11.4
  edge band (0.0, 0.01]                                          bets=119 W=60 L=59 P=0 units=-8.74 ret%=-6.25 lo%=-20.66 hi%=7.71
  edge band (0.01, 0.02]                                         bets=64 W=37 L=27 P=0 units=5.12 ret%=6.57 lo%=-11.15 hi%=25.07
  edge band (0.02, 0.03]                                         bets=40 W=24 L=16 P=0 units=4.78 ret%=9.65 lo%=-13.53 hi%=35.29
  edge band (0.03, 0.05]                                         bets=17 W=12 L=5 P=0 units=6.2 ret%=29.95 lo%=-3.85 hi%=60.09
  edge band (0.05, 1.0]                                          bets=2 W=1 L=1 P=0 units=-0.13 ret%=-5.63 lo%=-100.0 hi%=84.75
  -- season 2026 (fit a = 1.476, b = 0.2412, 621 games)
  read at T-360                                                  bets=47 W=32 L=15 P=0 units=14.88 ret%=26.14 lo%=8.07 hi%=43.0
  read at T-180                                                  bets=50 W=34 L=16 P=0 units=15.6 ret%=25.74 lo%=5.17 hi%=44.32
  read at T-120                                                  bets=46 W=31 L=15 P=0 units=12.73 ret%=21.99 lo%=1.58 hi%=41.43
  read at T-60                                                   bets=49 W=34 L=15 P=0 units=16.35 ret%=26.58 lo%=8.5 hi%=44.0
  read at T-30                                                   bets=46 W=32 L=14 P=0 units=15.38 ret%=26.83 lo%=5.67 hi%=45.55
  read at T-10                                                   bets=55 W=34 L=21 P=0 units=9.05 ret%=13.34 lo%=-7.97 hi%=33.5
  -- season 2027 (fit a = -7.826, b = 0.2978, 1023 games)
  read at T-360                                                  bets=1 W=1 L=0 P=0 units=1.0 ret%=77.52 lo%=77.52 hi%=77.52
  read at T-180                                                  bets=1 W=1 L=0 P=0 units=1.0 ret%=77.52 lo%=77.52 hi%=77.52
  read at T-120                                                  bets=4 W=2 L=2 P=0 units=-0.64 ret%=-12.52 lo%=-56.55 hi%=34.34
  read at T-60                                                   bets=3 W=2 L=1 P=0 units=0.66 ret%=17.32 lo%=-43.52 hi%=82.19
  read at T-30                                                   bets=2 W=2 L=0 P=0 units=2.0 ret%=87.72 lo%=84.75 hi%=90.91
  read at T-10                                                   bets=4 W=3 L=1 P=0 units=1.8 ret%=38.63 lo%=-8.77 hi%=88.5
  season 2025, offshore books (reference)                        bets=12 W=6 L=6 P=0 units=-1.25 ret%=-8.71 lo%=-54.48 hi%=37.81
  placebo (anchor shuffled across graded games, 200x): mean -8.08%, p95 -0.47%, real +13.34% sits at percentile 100.0

==== h2h_h1: V1 (2025-26 time split, US consensus anchor), decidable books ====
  frozen fit: a = 0.128, b = 0.2946 on 201 games
  as run (T-10, cut 0.02)                                        bets=121 W=45 L=74 P=2 units=5.3 ret%=4.4 lo%=-16.55 hi%=24.35
  side split: {'away': 66, 'home': 55}; prices median 190, shortest -118; books {'betrivers': 97, 'fanduel': 23, 'betmgm': 1}
  blind away at the best decidable price, same graded games      bets=201 W=86 L=111 P=4 units=-8.55 ret%=-3.64 lo%=-16.21 hi%=8.47
  early half of the bets (by date)                               bets=60 W=26 L=34 P=0 units=13.63 ret%=22.53 lo%=-5.85 hi%=50.78
  late half of the bets (by date)                                bets=61 W=19 L=40 P=2 units=-8.33 ret%=-13.92 lo%=-41.13 hi%=13.29
  without the 10 best dates                                      bets=97 W=25 L=71 P=1 units=-26.72 ret%=-27.45 lo%=-45.43 hi%=-11.99
  edge band (0.0, 0.01]                                          bets=19 W=6 L=12 P=1 units=-7.75 ret%=-36.5 lo%=-65.83 hi%=-8.18
  edge band (0.01, 0.02]                                         bets=18 W=6 L=12 P=0 units=-4.08 ret%=-21.5 lo%=-59.76 hi%=21.79
  edge band (0.02, 0.03]                                         bets=21 W=6 L=14 P=1 units=-6.02 ret%=-28.65 lo%=-68.22 hi%=9.61
  edge band (0.03, 0.05]                                         bets=39 W=18 L=20 P=1 units=8.6 ret%=22.43 lo%=-12.21 hi%=58.36
  edge band (0.05, 1.0]                                          bets=61 W=21 L=40 P=0 units=2.72 ret%=4.46 lo%=-21.62 hi%=34.17
  read at T-360                                                  bets=118 W=44 L=73 P=1 units=5.62 ret%=4.76 lo%=-17.16 hi%=25.15
  read at T-180                                                  bets=118 W=45 L=71 P=2 units=8.53 ret%=7.29 lo%=-11.67 hi%=25.54
  read at T-120                                                  bets=117 W=44 L=71 P=2 units=7.82 ret%=6.76 lo%=-13.64 hi%=28.3
  read at T-60                                                   bets=121 W=45 L=74 P=2 units=5.87 ret%=4.9 lo%=-14.44 hi%=24.24
  read at T-30                                                   bets=121 W=45 L=74 P=2 units=5.77 ret%=4.81 lo%=-15.5 hi%=24.41
  read at T-10                                                   bets=121 W=45 L=74 P=2 units=5.3 ret%=4.4 lo%=-16.55 hi%=24.35
  fit on every season available (Pinnacle anchor, 822 games): a = 0.351, b = 0.4330
    -> graded on the same second half of 2025-26                 bets=71 W=23 L=48 P=0 units=-13.23 ret%=-17.68 lo%=-39.17 hi%=5.69
  frozen V1 fit, Pinnacle anchor, same second half (anchor check) bets=126 W=47 L=77 P=2 units=5.23 ret%=4.18 lo%=-15.76 hi%=22.41
  frozen V1 fit on 2026-27 to date, decidable books              bets=50 W=19 L=29 P=2 units=1.2 ret%=2.49 lo%=-23.02 hi%=25.48
  frozen V1 fit on 2023-24, offshore books (reference)           bets=60 W=17 L=41 P=2 units=-10.82 ret%=-18.56 lo%=-46.77 hi%=10.49
  frozen V1 fit on 2024-25, offshore books (reference)           bets=115 W=39 L=73 P=3 units=-12.18 ret%=-10.77 lo%=-31.93 hi%=10.97
  placebo (anchor shuffled across graded games, 200x): mean -0.19%, p95 +7.21%, real +4.40% sits at percentile 84.5

==== totals_q1: V1 (2025-26 time split, US consensus anchor), decidable books ====
  frozen fit: a = -16.906, b = 0.3508 on 201 games
  as run (T-10, cut 0.02)                                        bets=18 W=12 L=6 P=0 units=5.78 ret%=30.61 lo%=-2.2 hi%=63.04
  side split: {'under': 13, 'over': 5}; prices median -104, shortest -113; books {'fanduel': 18}
  blind under at the best decidable price, same graded games     bets=199 W=98 L=101 P=0 units=-13.57 ret%=-6.14 lo%=-17.56 hi%=5.05
  early half of the bets (by date)                               bets=9 W=5 L=4 P=0 units=0.84 ret%=8.94 lo%=-40.77 hi%=52.23
  late half of the bets (by date)                                bets=9 W=7 L=2 P=0 units=4.94 ret%=52.11 lo%=9.23 hi%=94.44
  without the 10 best dates                                      bets=8 W=2 L=6 P=0 units=-4.22 ret%=-50.3 lo%=-100.0 hi%=-1.89
  edge band (0.0, 0.01]                                          bets=34 W=19 L=15 P=0 units=2.52 ret%=6.73 lo%=-16.05 hi%=29.29
  edge band (0.01, 0.02]                                         bets=17 W=8 L=9 P=0 units=-2.0 ret%=-10.75 lo%=-53.62 hi%=30.47
  edge band (0.02, 0.03]                                         bets=13 W=10 L=3 P=0 units=6.88 ret%=50.4 lo%=14.34 hi%=80.53
  edge band (0.03, 0.05]                                         bets=5 W=2 L=3 P=0 units=-1.1 ret%=-21.03 lo%=-100.0 hi%=56.44
  read at T-360                                                  bets=6 W=4 L=2 P=0 units=1.96 ret%=30.29 lo%=-33.02 hi%=90.1
  read at T-180                                                  bets=9 W=5 L=4 P=0 units=0.88 ret%=9.44 lo%=-35.19 hi%=52.79
  read at T-120                                                  bets=13 W=8 L=5 P=0 units=3.15 ret%=23.25 lo%=-24.59 hi%=65.69
  read at T-60                                                   bets=11 W=7 L=4 P=0 units=2.84 ret%=24.55 lo%=-28.23 hi%=60.73
  read at T-30                                                   bets=12 W=7 L=5 P=0 units=1.8 ret%=14.27 lo%=-29.34 hi%=58.7
  read at T-10                                                   bets=18 W=12 L=6 P=0 units=5.78 ret%=30.61 lo%=-2.2 hi%=63.04
  fit on every season available (Pinnacle anchor, 822 games): a = -3.958, b = 0.2743
    -> graded on the same second half of 2025-26                 bets=10 W=6 L=4 P=0 units=1.63 ret%=14.46 lo%=-39.94 hi%=53.79
  frozen V1 fit, Pinnacle anchor, same second half (anchor check) bets=24 W=15 L=9 P=0 units=5.59 ret%=21.81 lo%=-13.31 hi%=57.73
  frozen V1 fit on 2026-27 to date, decidable books              bets=4 W=2 L=2 P=0 units=-0.3 ret%=-6.79 lo%=-63.83 hi%=94.94
  frozen V1 fit on 2023-24, offshore books (reference)           bets=127 W=66 L=61 P=0 units=-6.58 ret%=-4.36 lo%=-17.63 hi%=8.13
  frozen V1 fit on 2024-25, offshore books (reference)           bets=15 W=6 L=9 P=0 units=-4.85 ret%=-26.94 lo%=-63.64 hi%=10.06
  placebo (anchor shuffled across graded games, 200x): mean -9.37%, p95 +1.01%, real +30.61% sits at percentile 100.0

==== h2h_h1: the blind underdog at the best decidable price, T-10 ====
  pooled 2025-26 + 2026-27                                       bets=465 W=192 L=258 P=15 units=19.14 ret%=4.22 lo%=-4.64 hi%=12.35
  season 2026                                                    bets=358 W=153 L=194 P=11 units=29.27 ret%=8.38 lo%=-1.85 hi%=19.57
  season 2027                                                    bets=107 W=39 L=64 P=4 units=-10.13 ret%=-9.76 lo%=-22.81 hi%=3.24
  2025-26 early half                                             bets=174 W=75 L=92 P=7 units=13.68 ret%=8.14 lo%=-6.2 hi%=23.9
  2025-26 late half                                              bets=184 W=78 L=102 P=4 units=15.59 ret%=8.6 lo%=-5.92 hi%=22.89
  without the 10 best dates                                      bets=419 W=158 L=250 P=11 units=-24.18 ret%=-5.89 lo%=-13.44 hi%=1.27
  side split: home dogs 134, away dogs 331
    away underdogs                                               bets=331 W=127 L=195 P=9 units=-1.36 ret%=-0.42 lo%=-11.05 hi%=10.14
    home underdogs                                               bets=134 W=65 L=63 P=6 units=20.5 ret%=15.84 lo%=-0.98 hi%=32.37
  price band (-300, 100]                                         bets=61 W=36 L=25 P=0 units=9.75 ret%=15.22 lo%=-6.77 hi%=35.7
  price band (100, 150]                                          bets=204 W=85 L=109 P=10 units=-5.68 ret%=-2.93 lo%=-16.96 hi%=9.22
  price band (150, 200]                                          bets=108 W=45 L=60 P=3 units=19.27 ret%=18.35 lo%=-2.76 hi%=39.56
  price band (200, 300]                                          bets=74 W=26 L=46 P=2 units=13.8 ret%=19.17 lo%=-8.21 hi%=48.02
  price band (300, 5000]                                         bets=18 W=0 L=18 P=0 units=-18.0 ret%=-100.0 lo%=-100.0 hi%=-100.0
```

## 8. Structural checks: do the books disagree at the same mark?

**Rarely across the US/offshore divide, often within the decidable books, and
mostly because of the rung problem.** At T-10 the decidable books' median
differs from the offshore median by 1+ points on 4.7% of first-half spread
games and about 17% of first-half total games (2025-26 and 2026-27).
Disagreement inside the decidable set looks large (62% of 2026-27 first-half
spread games 1+ points apart), but FanDuel's own first-half spread sits 1+
points off the other books on 12.8% of its 2025-26 quotes and 3.4% in 2026-27,
while BetMGM 2026-27 and Fanatics 2025-26 sit off on nearly all of theirs
(section 2). **Betting against a decidable book standing 1+ points off the
others loses or breaks even at every threshold** (T-10, threshold 1.0:
first-half spread -0.24% on 228, first-half total -6.78% on 313, first-quarter
spread -7.45% on 158, first-quarter total -14.25% on 142; the only positive
cells, first-quarter spreads at 1.5 and 2.0 points, +2.75% on 94 and +4.12% on
70, are mostly Fanatics rungs (57 of 94, 47 of 70) and their intervals run
from about -12% to +21%). The off-centre rungs themselves carry their own margin: blind on the
long-priced side -12.35% (415 bets, median +215), on the short-priced side
-6.69% (415, median -325).

Printed by `scripts/euroleague_research/r1_structure.py`:

```
==== disagreement at the same mark: share of (game, mark) with the books' numbers 1+ / 2+ points apart ====
    market  season   mark               compare  games  share_ge1  share_ge2  max_gap
spreads_h1    2025   T-10             all books    257      0.163      0.008  2.00000
spreads_h1    2025 T-1440             all books     40      0.100      0.025  2.00000
spreads_h1    2025  T-360             all books    233      0.193      0.013  7.00000
spreads_h1    2026   T-10             all books    395      0.435      0.089  6.49750
spreads_h1    2026   T-10        decidable only    313      0.476      0.112  6.49750
spreads_h1    2026   T-10 decidable vs offshore    316      0.047      0.003  2.24775
spreads_h1    2026 T-1440             all books    326      0.429      0.028  8.49450
spreads_h1    2026 T-1440        decidable only    310      0.419      0.019  8.49450
spreads_h1    2026 T-1440 decidable vs offshore    312      0.064      0.000  1.50000
spreads_h1    2026  T-360             all books    393      0.468      0.117  8.49550
spreads_h1    2026  T-360        decidable only    314      0.519      0.140  8.49550
spreads_h1    2026  T-360 decidable vs offshore    316      0.057      0.000  1.75000
spreads_h1    2027   T-10             all books    107      0.682      0.458  5.00000
spreads_h1    2027   T-10        decidable only    106      0.623      0.443  5.00000
spreads_h1    2027   T-10 decidable vs offshore    107      0.047      0.000  1.00000
spreads_h1    2027 T-1440             all books    106      0.642      0.434  6.00000
spreads_h1    2027 T-1440        decidable only    102      0.637      0.451  6.00000
spreads_h1    2027 T-1440 decidable vs offshore    104      0.077      0.010  2.00000
spreads_h1    2027  T-360             all books    107      0.701      0.458  5.00000
spreads_h1    2027  T-360        decidable only    106      0.632      0.453  5.00000
spreads_h1    2027  T-360 decidable vs offshore    107      0.028      0.009  2.00000
 totals_h1    2025   T-10             all books    259      0.293      0.023  2.00000
 totals_h1    2025 T-1440             all books     39      0.256      0.026  2.00000
 totals_h1    2025  T-360             all books    234      0.299      0.043  2.00000
 totals_h1    2026   T-10             all books    395      0.635      0.170  6.00000
 totals_h1    2026   T-10        decidable only    311      0.588      0.145  6.00000
 totals_h1    2026   T-10 decidable vs offshore    316      0.174      0.013  2.50000
 totals_h1    2026 T-1440             all books    326      0.666      0.101  4.50000
 totals_h1    2026 T-1440        decidable only    308      0.506      0.062  3.00000
 totals_h1    2026 T-1440 decidable vs offshore    312      0.288      0.013  2.50000
 totals_h1    2026  T-360             all books    394      0.624      0.203  4.50000
 totals_h1    2026  T-360        decidable only    312      0.574      0.196  4.00000
 totals_h1    2026  T-360 decidable vs offshore    316      0.174      0.022  3.00000
 totals_h1    2027   T-10             all books    107      0.682      0.252  7.00000
 totals_h1    2027   T-10        decidable only    106      0.566      0.245  6.00000
 totals_h1    2027   T-10 decidable vs offshore    107      0.168      0.009  2.00000
 totals_h1    2027 T-1440             all books    104      0.596      0.154  7.00000
 totals_h1    2027 T-1440        decidable only     99      0.545      0.141  7.00000
 totals_h1    2027 T-1440 decidable vs offshore    104      0.212      0.000  1.50000
 totals_h1    2027  T-360             all books    107      0.701      0.215  6.50000
 totals_h1    2027  T-360        decidable only    105      0.543      0.181  6.00000
 totals_h1    2027  T-360 decidable vs offshore    107      0.131      0.000  1.50000
spreads_q1    2026   T-10             all books    313      0.597      0.201  4.00000
spreads_q1    2026   T-10        decidable only    313      0.597      0.201  4.00000
spreads_q1    2026 T-1440             all books    310      0.500      0.013  2.49750
spreads_q1    2026 T-1440        decidable only    310      0.500      0.013  2.49750
spreads_q1    2026  T-360             all books    314      0.605      0.086  3.00000
spreads_q1    2026  T-360        decidable only    314      0.605      0.086  3.00000
spreads_q1    2027   T-10             all books    106      0.208      0.038  3.00000
spreads_q1    2027   T-10        decidable only    106      0.208      0.038  3.00000
spreads_q1    2027 T-1440             all books     99      0.273      0.040  4.00000
spreads_q1    2027 T-1440        decidable only     99      0.273      0.040  4.00000
spreads_q1    2027  T-360             all books    105      0.210      0.038  4.00000
spreads_q1    2027  T-360        decidable only    105      0.210      0.038  4.00000
 totals_q1    2026   T-10             all books    221      0.548      0.262  4.00000
 totals_q1    2026   T-10        decidable only    221      0.548      0.262  4.00000
 totals_q1    2026 T-1440             all books    220      0.350      0.000  1.00000
 totals_q1    2026 T-1440        decidable only    220      0.350      0.000  1.00000
 totals_q1    2026  T-360             all books    224      0.549      0.112  2.00000
 totals_q1    2026  T-360        decidable only    224      0.549      0.112  2.00000
 totals_q1    2027   T-10             all books    106      0.340      0.000  1.00000
 totals_q1    2027   T-10        decidable only    106      0.340      0.000  1.00000

==== the outlier rule: bet against a decidable book standing 1+ points off the others ====
    market mark  threshold   seasons                       sides                                                           books  bets   W   L  P  units   ret%    lo%   hi%
spreads_h1 T-10        1.0 2026,2027  {'away': 121, 'home': 107} {'betmgm': 135, 'fanduel': 49, 'fanatics': 26, 'betrivers': 18}   228 138  90  0  -0.87  -0.24  -8.74  8.31
spreads_h1 T-10        1.5 2026,2027    {'away': 65, 'home': 19}                  {'betmgm': 56, 'fanatics': 26, 'betrivers': 2}    84  51  33  0 -14.65  -8.65 -19.39  2.90
spreads_h1 T-10        2.0 2026,2027    {'away': 63, 'home': 19}                  {'betmgm': 54, 'fanatics': 26, 'betrivers': 2}    82  50  32  0 -14.20  -8.54 -19.74  3.19
spreads_h1 T-60        1.0 2026,2027  {'away': 125, 'home': 107} {'betmgm': 142, 'fanduel': 41, 'fanatics': 27, 'betrivers': 22}   232 139  93  0  -6.08  -1.66  -9.28  6.21
spreads_h1 T-60        1.5 2026,2027    {'away': 65, 'home': 22}    {'betmgm': 55, 'fanatics': 27, 'betrivers': 4, 'fanduel': 1}    87  53  34  0 -15.44  -8.73 -18.24  1.07
spreads_h1 T-60        2.0 2026,2027    {'away': 64, 'home': 19}    {'betmgm': 53, 'fanatics': 27, 'betrivers': 2, 'fanduel': 1}    83  52  31  0 -12.05  -7.05 -16.66  2.69
 totals_h1 T-10        1.0 2026,2027 {'over': 184, 'under': 129} {'betmgm': 178, 'fanduel': 71, 'betrivers': 35, 'fanatics': 29}   313 168 145  0 -29.61  -6.78 -14.20  1.15
 totals_h1 T-10        1.5 2026,2027   {'under': 46, 'over': 43}    {'betmgm': 46, 'fanatics': 29, 'fanduel': 8, 'betrivers': 6}    89  49  40  0 -16.50 -10.61 -21.82  0.74
 totals_h1 T-10        2.0 2026,2027   {'under': 39, 'over': 30}    {'betmgm': 30, 'fanatics': 29, 'fanduel': 5, 'betrivers': 5}    69  41  28  0  -8.82  -6.80 -19.24  5.97
 totals_h1 T-60        1.0 2026,2027 {'over': 182, 'under': 122} {'betmgm': 173, 'fanduel': 65, 'betrivers': 35, 'fanatics': 31}   304 168 136  0 -18.68  -4.37 -11.46  2.36
 totals_h1 T-60        1.5 2026,2027   {'under': 42, 'over': 41}    {'betmgm': 37, 'fanatics': 31, 'betrivers': 9, 'fanduel': 6}    83  48  35  0 -10.60  -7.12 -18.57  4.99
 totals_h1 T-60        2.0 2026,2027   {'under': 36, 'over': 30}    {'fanatics': 31, 'betmgm': 28, 'betrivers': 5, 'fanduel': 2}    66  41  25  0  -4.14  -3.27 -15.88  8.95
spreads_q1 T-10        1.0 2026,2027    {'home': 83, 'away': 75}   {'fanatics': 58, 'betmgm': 52, 'fanduel': 44, 'betrivers': 4}   158  84  74  0 -17.27  -7.45 -13.29 -1.32
spreads_q1 T-10        1.5 2026,2027    {'away': 49, 'home': 45}   {'fanatics': 57, 'betmgm': 21, 'fanduel': 13, 'betrivers': 3}    94  60  34  0   4.38   2.75 -10.08 14.37
spreads_q1 T-10        2.0 2026,2027    {'away': 39, 'home': 31}    {'fanatics': 47, 'betmgm': 21, 'fanduel': 1, 'betrivers': 1}    70  47  23  0   5.15   4.12 -12.04 21.07
spreads_q1 T-60        1.0 2026,2027    {'home': 79, 'away': 74}   {'fanatics': 58, 'betmgm': 51, 'fanduel': 40, 'betrivers': 4}   153  80  73  0 -20.71  -9.10 -15.08 -2.93
spreads_q1 T-60        1.5 2026,2027    {'away': 50, 'home': 48}   {'fanatics': 57, 'betmgm': 24, 'fanduel': 13, 'betrivers': 4}    98  62  36  0   3.72   2.26  -9.20 13.77
spreads_q1 T-60        2.0 2026,2027    {'away': 39, 'home': 35}    {'fanatics': 46, 'betmgm': 24, 'betrivers': 3, 'fanduel': 1}    74  48  26  0   2.92   2.25 -12.82 17.62
 totals_q1 T-10        1.0      2026   {'under': 75, 'over': 67}                   {'fanatics': 58, 'betmgm': 45, 'fanduel': 39}   142  71  71  0 -29.68 -14.25 -18.78 -9.90
 totals_q1 T-10        1.5      2026   {'over': 49, 'under': 41}                   {'fanatics': 58, 'betmgm': 19, 'fanduel': 13}    90  51  39  0 -13.04  -8.76 -13.92 -2.86
 totals_q1 T-10        2.0      2026   {'over': 36, 'under': 28}                                  {'fanatics': 45, 'betmgm': 19}    64  38  26  0  -6.08  -5.50 -12.23  1.49
 totals_q1 T-60        1.0      2026   {'under': 77, 'over': 68}                   {'fanatics': 58, 'betmgm': 46, 'fanduel': 41}   145  72  73  0 -30.32 -14.37 -19.14 -9.75
 totals_q1 T-60        1.5      2026   {'over': 48, 'under': 39}                   {'fanatics': 58, 'betmgm': 17, 'fanduel': 12}    87  50  37  0 -11.04  -7.65 -13.12 -2.11
 totals_q1 T-60        2.0      2026   {'over': 36, 'under': 27}                                  {'fanatics': 46, 'betmgm': 17}    63  38  25  0  -4.88  -4.48 -11.36  2.25

-- by season, threshold 1.0, T-10
    market  season  bets   W   L  P  units   ret%    lo%   hi%
spreads_h1    2026   162  99  63  0  12.10   5.24  -5.20 15.02
spreads_h1    2027    66  39  27  0 -12.97 -10.39 -22.90  3.85
spreads_q1    2026   147  78  69  0 -14.78  -6.86 -13.40 -0.06
spreads_q1    2027    11   6   5  0  -2.49 -15.01 -27.59 -4.49
 totals_h1    2026   248 130 118  0 -26.98  -8.06 -16.59  0.90
 totals_h1    2027    65  38  27  0  -2.63  -2.57 -16.57 10.49
 totals_q1    2026   142  71  71  0 -29.68 -14.25 -18.78 -9.90

==== off-centre 'main' quotes at T-10, each side bet blind at its own price ====
    market     book  season  side             which  median_price  bets  W  L  P  units    ret%     lo%     hi%
spreads_h1   betmgm    2026  home  long-priced side         172.5     2  0  2  0  -2.00 -100.00 -100.00 -100.00
spreads_h1   betmgm    2026  away short-priced side        -262.5     2  2  0  0   2.00   38.10   36.36   40.00
spreads_h1   betmgm    2027  home  long-priced side         190.0    56 17 39  0  -4.20   -7.50  -35.97   17.38
spreads_h1   betmgm    2027  home short-priced side        -300.0     1  1  0  0   1.00   33.33   33.33   33.33
spreads_h1   betmgm    2027  away  long-priced side         200.0     1  0  1  0  -1.00 -100.00 -100.00 -100.00
spreads_h1   betmgm    2027  away short-priced side        -295.0    56 39 17  0 -10.68   -6.77  -17.31    5.69
spreads_h1 fanatics    2026  home  long-priced side         190.0    24  7 17  0  -2.95  -12.29  -57.62   33.96
spreads_h1 fanatics    2026  home short-priced side        -267.5     8  5  3  0  -3.45  -16.24  -47.56   17.61
spreads_h1 fanatics    2026  away  long-priced side         192.5     8  3  5  0   1.25   15.62  -55.00   84.36
spreads_h1 fanatics    2026  away short-priced side        -270.0    24 17  7  0  -2.33   -3.56  -24.73   17.19
spreads_q1   betmgm    2026  home  long-priced side         210.0     3  1  2  0  -0.20   -6.67 -100.00   40.00
spreads_q1   betmgm    2026  away short-priced side        -325.0     3  2  1  0  -0.90  -10.33  -31.77   30.77
spreads_q1   betmgm    2027  home  long-priced side         220.0    99 35 64  0  11.75   11.87  -13.01   37.34
spreads_q1   betmgm    2027  home short-priced side        -375.0     1  1  0  0   0.80   26.67   26.67   26.67
spreads_q1   betmgm    2027  away  long-priced side         240.0     1  0  1  0  -1.00 -100.00 -100.00 -100.00
spreads_q1   betmgm    2027  away short-priced side        -350.0    99 64 35  0 -48.72  -16.67  -26.84   -6.85
 totals_h1   betmgm    2026  over  long-priced side         250.0     3  1  2  0   0.50   16.67 -100.00   75.00
 totals_h1   betmgm    2026 under short-priced side        -425.0     3  2  1  0  -1.96  -21.79  -38.24   11.11
 totals_h1   betmgm    2027  over  long-priced side         200.0    82 18 64  0 -28.15  -34.33  -54.58  -12.32
 totals_h1   betmgm    2027 under short-priced side        -300.0    82 64 18  0   4.48    1.87   -8.00   11.06
 totals_h1 fanatics    2026  over  long-priced side         185.0    11  5  6  0   3.05   27.73  -45.00   96.54
 totals_h1 fanatics    2026  over short-priced side        -260.0    18 11  7  0  -7.45  -15.75  -41.99   18.53
 totals_h1 fanatics    2026 under  long-priced side         185.0    18  7 11  0   2.20   12.22  -59.29   68.55
 totals_h1 fanatics    2026 under short-priced side        -260.0    11  6  5  0  -6.80  -23.99  -57.26   11.54
 totals_q1   betmgm    2026  over  long-priced side         375.0     3  1  2  0   1.75   58.33 -100.00  137.50
 totals_q1   betmgm    2026 under short-priced side        -700.0     3  2  1  0  -2.42  -26.90  -42.86    5.00
 totals_q1   betmgm    2027  over  long-priced side         290.0   104 19 85  0 -32.25  -31.01  -50.77  -11.10
 totals_q1   betmgm    2027 under short-priced side        -500.0   104 85 19  0  -3.96   -1.27   -7.41    5.06

-- pooled over every off-centre quote at T-10:
  long-priced side   {'bets': 415, 'W': 114, 'L': 301, 'P': 0, 'units': -51.25, 'ret%': -12.35, 'lo%': np.float64(-25.01), 'hi%': np.float64(0.29)} median price 215.0
  short-priced side  {'bets': 415, 'W': 301, 'L': 114, 'P': 0, 'units': -80.39, 'ret%': -6.69, 'lo%': np.float64(-11.65), 'hi%': np.float64(-1.65)} median price -325.0
```

## 9. What the sample can resolve

About 2,700 bets resolves a return to roughly +/-4 points. The decidable
history is about 423 games a market (2025-26 plus 2026-27 to date): the
measured 90% half-width on a pooled blind side is about 7-9 points, one season
(316-358 games) about 8-11, and a cut that keeps 50 bets about 20. The offshore
reference over three seasons (about 1,090 bets at BetUS) resolves to about +/-4
(90%) but cannot be bet. **Nothing in this round can resolve an edge of the
size these markets would plausibly hold (a few points);** a result has to be
large and pass the kill tests to mean anything, and none did. 2026-27 adds
about 270 more regular-season games by May.

## 10. What to test next

1. **The first-quarter under lead (P2)**, frozen as it stands (fit on 2023-24
   to 2025-26, cut 0.02, T-10, decidable books) and read unchanged on 2026-27
   as it is played; it bet 4 games of the first 107, so the read needs most
   of the season. Its control row is already negative (section 7), so what it
   still has to show is a second season and both sides of the total.
2. **The home underdog in the first half**: the moneyline (+15.8% on 134) and
   the spread band (home covered 58.9% of 175 games as a 0-4 point full-game
   underdog). Both were found after looking, so test them on what they did not
   come from: 2023-24 and 2024-25 at the offshore books, and 2026-27 forward;
   check relocated "home" games (Belgrade, Sofia, Sarajevo) are not driving it.
3. **The moneyline close's calibration** (slope 0.877 first half, 0.751 first
   quarter at the decidable books): a market-anchored shrink of the de-vigged
   probability toward 50%, fitted on 2025-26 and read on 2026-27.
4. **V1 on more seasons** once the 2023-24 and 2024-25 full-game spool is in,
   with the team half-tendency term restored; a slope fitted on one season is
   what killed P1.
5. **Fix the stored main number for BetMGM 2026-27 and Fanatics 2025-26**
   before any book-specific result is read; BetMGM is half the 2026-27
   decidable first-quarter moneyline coverage.
6. **The three-way first-half market**: BetRivers prices the first-half draw at
   a fair 4.8% and the first-quarter draw at 6.5%, against realised tie rates
   of 3.4% and 6.3%. Check whether the three-way sides are cheaper than the
   two-way ones on the same games (a low-priority price check, not an edge
   claim).
