"""Do US Hong Kong payouts equal the Hong Kong Jockey Club's own dividends?

A bet that joins the Club's pool is paid the Club's dividend, so a US $2 payout
should equal the dividend per HK$10 divided by five. This compares the two, race
by race, in exact decimals, for two November 2026 meetings. It reads nothing from
the web: the figures below were copied from the pages on 2026-11-17.

Club figures: racing.hkjc.com LocalResults pages (by date, course and race).
US figures: offtrackbetting.com results pages (track 452 Sha Tin, 451 Happy
Valley), opened in a browser (the site refuses automated fetches). The US page
numbers the Sha Tin races 1-10 because the Club's race 6 was abandoned.
Write-up: docs/horse_racing_scout_us_outlets.md, "Measured, 2026-11-17".

    python -I scripts/horse/hk_pooling_check.py
"""
from decimal import Decimal as D

# (club race, [(horse, win_or_None, place)]) ; US list in OTB race order
CLUB_ST = {
    1: {12: ("347.00", "73.50"), 2: (None, "13.50"), 8: (None, "23.00")},
    2: {9: ("44.50", "18.00"), 6: (None, "19.50"), 10: (None, "23.00")},
    3: {4: ("87.00", "26.50"), 5: (None, "22.00"), 13: (None, "16.50")},
    4: {7: ("194.50", "47.50"), 13: (None, "60.00"), 1: (None, "12.00")},
    5: {12: ("309.50", "56.00"), 9: (None, "80.50"), 2: (None, "10.50")},
    7: {9: ("347.50", "40.00"), 8: (None, "11.50"), 6: (None, "33.00"), 13: (None, "10.10")},
    8: {4: ("387.50", "103.00"), 7: (None, "34.50"), 2: (None, "59.50")},
    9: {10: ("60.00", "20.50"), 7: (None, "20.50"), 8: (None, "47.50")},
    10: {12: ("118.00", "38.50"), 13: (None, "45.50"), 5: (None, "74.50")},
    11: {11: ("54.50", "19.00"), 9: (None, "24.50"), 12: (None, "24.00")},
}
US_ST = [
    {12: ("69.40", "14.70"), 2: (None, "2.70"), 8: (None, "4.60")},
    {9: ("8.90", "3.60"), 6: (None, "3.90"), 10: (None, "4.60")},
    {4: ("17.40", "5.30"), 5: (None, "4.40"), 13: (None, "3.30")},
    {7: ("38.90", "9.50"), 13: (None, "12.00"), 1: (None, "2.40")},
    {12: ("61.90", "11.20"), 9: (None, "16.10"), 2: (None, "2.10")},
    {9: ("69.50", "8.00"), 8: (None, "2.30"), 6: (None, "6.60"), 13: (None, "2.02")},
    {4: ("77.50", "20.60"), 7: (None, "6.90"), 2: (None, "11.90")},
    {10: ("12.00", "4.10"), 7: (None, "4.10"), 8: (None, "9.50")},
    {12: ("23.60", "7.70"), 13: (None, "9.10"), 5: (None, "14.90")},
    {11: ("10.90", "3.80"), 9: (None, "4.90"), 12: (None, "4.80")},
]
CLUB_HV = {
    1: {5: ("109.00", "33.00"), 6: (None, "17.00"), 11: (None, "27.00")},
    2: {7: ("150.50", "44.00"), 4: (None, "19.50"), 10: (None, "22.00")},
    3: {3: ("104.50", "30.00"), 2: (None, "20.50"), 8: (None, "61.50")},
    4: {11: ("44.00", "17.50"), 7: (None, "18.00"), 1: (None, "33.50")},
    5: {8: ("164.50", "44.00"), 10: (None, "14.50"), 3: (None, "30.00")},
    6: {11: ("58.50", "21.50"), 7: (None, "17.50"), 1: (None, "41.50")},
    7: {5: ("39.50", "16.50"), 7: (None, "17.50"), 8: (None, "55.50")},
    8: {1: ("105.50", "30.00"), 11: (None, "51.50"), 4: (None, "57.50")},
    9: {3: ("101.50", "30.50"), 7: (None, "33.00"), 2: (None, "108.50")},
}
US_HV = [
    {5: ("21.80", "6.60"), 6: (None, "3.40"), 11: (None, "5.40")},
    {7: ("30.10", "8.80"), 4: (None, "3.90"), 10: (None, "4.40")},
    {3: ("20.90", "6.00"), 2: (None, "4.10"), 8: (None, "12.30")},
    {11: ("8.80", "3.50"), 7: (None, "3.60"), 1: (None, "6.70")},
    {8: ("32.90", "8.80"), 10: (None, "2.90"), 3: (None, "6.00")},
    {11: ("11.70", "4.30"), 7: (None, "3.50"), 1: (None, "8.30")},
    {5: ("7.90", "3.30"), 7: (None, "3.50"), 8: (None, "11.10")},
    {1: ("21.10", "6.00"), 11: (None, "10.30"), 4: (None, "11.50")},
    {3: ("20.30", "6.10"), 7: (None, "6.60"), 2: (None, "21.70")},
]
# Sha Tin race 1 exotics: (Club per HK$10, US payout, US stake)
EXOTIC_ST1 = [("QIN 2-12", "367.50", "7.35", "0.20"), ("QPL 2-12 / Omni", "128.50", "2.57", "0.20"),
              ("QPL 8-12 / Omni", "263.50", "5.27", "0.20"), ("QPL 2-8 / Omni", "40.50", "0.81", "0.20"),
              ("FC 12-2 / Exacta", "1278.00", "255.60", "2"), ("TCE 12-2-8 / Trifecta", "10361.00", "2072.20", "2"),
              ("TRIO 2-8-12", "717.00", "143.40", "2")]


def compare(name, club, us):
    n = bad = 0
    for (race, c), u in zip(sorted(club.items()), us):
        assert set(c) == set(u), (name, race, c, u)
        for horse in c:
            for kind, cv, uv in (("win", c[horse][0], u[horse][0]), ("place", c[horse][1], u[horse][1])):
                if cv is None:
                    assert uv is None
                    continue
                want = D(cv) / 5
                n += 1
                if want != D(uv):
                    bad += 1
                    print(f"  MISMATCH {name} R{race} #{horse} {kind}: club {cv}/5={want} us {uv}")
    print(f"{name}: {n} payouts compared, {bad} differ")
    return n, bad


def main() -> int:
    t1 = compare("Sha Tin 2026-11-14", CLUB_ST, US_ST)
    t2 = compare("Happy Valley 2026-11-11", CLUB_HV, US_HV)
    eb = 0
    for label, club, us, stake in EXOTIC_ST1:
        want = D(club) * D(stake) / 10
        eb += want != D(us)
        print(f"  {label}: club {club} x {stake}/10 = {want}  us {us}  {'same' if want == D(us) else 'DIFFERENT'}")
    print(f"exotics: {len(EXOTIC_ST1)} compared, {eb} differ")
    print(f"total win+place: {t1[0] + t2[0]} compared, {t1[1] + t2[1]} differ")
    return 1 if (t1[1] or t2[1] or eb) else 0


if __name__ == "__main__":
    raise SystemExit(main())
