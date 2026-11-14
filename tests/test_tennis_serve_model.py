"""The serve-and-return game model of scripts/tennis_serve_study.py: hold
probabilities, symmetric matches, distributions that sum to one, and a joint
whose marginals equal the marginal programmes."""
import numpy as np

from scripts import tennis_serve_study as m


def test_hold():
    assert abs(float(m.hold(0.5)) - 0.5) < 1e-12
    assert abs(float(m.hold(0.6)) - 0.7357) < 5e-5


def test_symmetric_players_win_half():
    p = np.array([0.55, 0.62, 0.70])
    for bo in (3, 5):
        assert np.allclose(m.match_win(p, p, np.full(3, bo)), 0.5, atol=1e-12)


def test_distributions_sum_to_one_and_agree_with_joint():
    pa, pb = np.array([0.66, 0.58]), np.array([0.61, 0.64])
    for bo in (3, 5):
        t, mg = m.distributions(pa, pb, np.full(2, bo))
        j = m.joint(pa, pb, np.full(2, bo))
        assert np.allclose(t.sum(1), 1) and np.allclose(mg.sum(1), 1) and np.allclose(j.sum((1, 2)), 1)
        tot = np.add.outer(np.arange(36), np.arange(36))
        assert np.allclose([[j[i][tot == k].sum() for k in range(m.NT)] for i in range(2)], t)


def test_anchor_hits_target_and_keeps_sum():
    d, pa, pb, miss, guard = m.anchor(np.full(3, 0.64), np.full(3, 0.60), np.full(3, 5), np.array([0.2, 0.5, 0.9]))
    assert miss.max() < 1e-6 and np.allclose(pa + pb, 1.24) and not guard.any()
