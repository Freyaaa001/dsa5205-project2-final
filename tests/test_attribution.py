"""Return-attribution identities and their agreement with the stored replay."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from usq.project2.attribution import (CHAIN, active_statistics, build, cagr,
                                      capm, chain_attribution)

RESULTS = Path(__file__).resolve().parents[1]/'results/project2_final'


def simulated(seed=5205, days=504):
    rng = np.random.default_rng(seed)
    market = rng.normal(4e-4, 1e-2, days)
    return market, {name: market*beta+rng.normal(drift, 4e-3, days)
                    for name, beta, drift in [('a', .9, 2e-4), ('b', 1.0, -1e-4), ('c', 1.0, 0)]}


def test_chain_links_sum_exactly_to_the_total():
    market, parts = simulated()
    series = {**parts, 'SPY': market}
    links = chain_attribution(series, ['a', 'b', 'c', 'SPY'])
    assert [r['link'] for r in links] == ['a-b', 'b-c', 'c-SPY']
    total = cagr(series['a'])-cagr(series['SPY'])
    np.testing.assert_allclose(sum(r['cagr_difference'] for r in links), total, atol=1e-14)


def test_chain_rejects_unknown_or_short_paths():
    market, parts = simulated()
    with pytest.raises(ValueError):
        chain_attribution(parts, ['a'])
    with pytest.raises(KeyError):
        chain_attribution(parts, ['a', 'missing'])


def test_capm_recovers_known_alpha_and_beta():
    rng = np.random.default_rng(1)
    market = rng.normal(5e-4, 1e-2, 2000)
    noise = rng.normal(0, 2e-3, 2000)
    noise -= noise.mean()+np.cov(noise, market)[0, 1]/market.var(ddof=1)*(market-market.mean())
    fit = capm(.0002+.8*market+noise, market)
    np.testing.assert_allclose(fit['beta'], .8, atol=1e-10)
    np.testing.assert_allclose(fit['alpha_annualized'], .0002*252, atol=1e-10)
    assert fit['alpha_t_hac'] > 2 and 0 < fit['residual_volatility'] < .05


def test_active_statistics_match_definitions():
    market, parts = simulated()
    stats = active_statistics(parts['a'], market)
    diff = parts['a']-market
    np.testing.assert_allclose(stats['tracking_error'], diff.std(ddof=1)*np.sqrt(252))
    np.testing.assert_allclose(stats['information_ratio'], diff.mean()/diff.std(ddof=1)*np.sqrt(252))
    np.testing.assert_allclose(stats['detectable_excess'], 2*stats['tracking_error']/np.sqrt(len(diff)/252))


def test_stored_replay_attribution_reconciles(tmp_path):
    frames = build(RESULTS, tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == {'attribution.csv', 'attribution_annual.csv',
                                                  'selection_by_weighting.csv', 'capm.csv'}
    summary = pd.read_csv(RESULTS/'portfolio_summary.csv').set_index(['case', 'phase'])
    table = frames['attribution'].set_index(['phase', 'link'])
    for phase in ['validation', 'evaluation']:
        row = summary.loc[(CHAIN[0], phase)]
        links = table.loc[phase]
        np.testing.assert_allclose(links.loc['total', 'cagr_difference'], row.annual_return_minus_spy, atol=1e-12)
        np.testing.assert_allclose(links.drop('total').cagr_difference.sum(), row.annual_return_minus_spy, atol=1e-12)
    # The total link must reproduce the interval already published in the report.
    published = pd.read_csv(RESULTS/'tables/paired_intervals.csv').query("a=='SPY' and block==20").iloc[0]
    total = table.loc[('evaluation', 'total')]
    np.testing.assert_allclose([total.ci_low, total.ci_high],
                               [published.cagr_diff_ci_low, published.cagr_diff_ci_high], atol=1e-12)
    annual = frames['annual']
    published_annual = pd.read_csv(RESULTS/'tables/annual.csv').query("case=='fundamental_sqrt_cap'")
    for r in published_annual.itertuples():
        got = annual.query("year==@r.year and link=='total'").return_difference.iloc[0]
        np.testing.assert_allclose(got, r.net_return-r.SPY_return, atol=1e-12)
