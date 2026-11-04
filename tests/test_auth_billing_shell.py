"""When AUTH is on, the shell is signed-in only. Flags stay false in source.

EAS sets EXPO_PUBLIC_AUTH_ENABLED and EXPO_PUBLIC_BILLING_ENABLED. A free
member keeps Record and the picks teaser. Signals and Live Signals open the
same paywall. A Whop-only my_access row does not unlock the app.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def _read(rel: str) -> str:
    return (MOBILE / rel).read_text(encoding="utf-8")


def test_flags_default_off_in_source():
    auth = _read("src/lib/authConfig.ts")
    billing = _read("src/lib/billingConfig.ts")
    assert "EXPO_PUBLIC_AUTH_ENABLED ?? 'false'" in auth
    assert "EXPO_PUBLIC_BILLING_ENABLED ?? 'false'" in billing
    assert "?? 'true'" not in auth
    assert "EXPO_PUBLIC_BILLING_ENABLED ?? 'true'" not in billing


def test_signed_out_navigation_returns_to_sign_in():
    app = _read("App.tsx")
    assert "readAuthStatus()" in app
    assert "signedOutRouteIsShell" in app
    assert 'routes: [{ name: \'SignIn\' }]' in app
    picks = app.split('name="Picks"')[1].split("/>")[0]
    assert "listeners={lockedTab}" not in picks


def test_signals_open_the_same_paywall():
    home = _read("src/screens/PicksHomeScreen.tsx")
    assert "freeSegmentOpensPaywall" in home
    assert "openPaywall()" in home
    push = _read("src/hooks/usePushDeepLink.ts")
    assert "readAuthStatus() === 'signedOut'" in push


def test_whop_only_row_cannot_stay_entitled():
    helpers = _read("src/lib/discordHelpers.ts")
    assert "source === 'discord'" in helpers
    assert "bool('entitled') && !whopOnly" in helpers
