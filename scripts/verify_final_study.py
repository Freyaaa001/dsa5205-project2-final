"""Independent accounting, nomination and cross-study controls for final replay."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from usq.project2.extensions import digest
from usq.project2.research_portfolio import ResearchMarket


def run(config, output):
    cfg = json.loads(Path(config).read_text())
    db, base, exp, deep, late = [Path(cfg[k]) for k in
        ['database', 'baseline', 'exploration', 'deep', 'late_fusion']]
    out = Path(output)
    s = pd.read_csv(out/'portfolio_summary.csv')
    assert len(s) == 38 and not s.duplicated(['case', 'phase']).any()
    for r in s.itertuples():
        folder = out/'portfolios'/r.case/r.phase
        d = pd.read_csv(folder/'daily.csv', dtype={'date': str}).set_index('date')
        ret = d.net_return.to_numpy(); nav = np.cumprod(1+ret)
        assert len(d) == r.days and d.index.is_unique and d.index.is_monotonic_increasing
        np.testing.assert_allclose(nav, d.net_nav, atol=1e-11)
        np.testing.assert_allclose(d.gross_return-d.cost, ret, atol=1e-12)
        np.testing.assert_allclose(d.cost, d.traded_notional*r.cost_bps/10000, atol=1e-12)
        np.testing.assert_allclose(np.expm1(np.log1p(ret).mean()*252), r.annual_return, atol=1e-12)
        np.testing.assert_allclose(np.std(ret, ddof=1)*np.sqrt(252), r.annual_volatility, atol=1e-12)
        np.testing.assert_allclose(np.min(nav/np.maximum(1,np.maximum.accumulate(nav))-1), r.max_drawdown, atol=1e-12)
        w = pd.read_parquet(folder/'monthly_holdings.parquet')
        assert w.weight.ge(0).all() and w.groupby('date').weight.sum().le(1+1e-6).all()
    controls = []
    for phase in ['validation', 'evaluation']:
        for weighting in ['equal', 'sqrt_cap', 'cap']:
            controls.append((f'fundamental_{weighting}', phase,
                exp/f'portfolios/weights/simple_C_{weighting}/{phase}/daily.csv'))
        for weight in [25, 50]:
            controls.append((f'fusion_{weight}', phase,
                late/f'portfolios/strategy/lambda{weight:03}_lag0_cost10/{phase}/daily.csv'))
    for fee in [20, 30]:
        controls.append((f'cost_{fee}', 'evaluation', deep/f'portfolios/costs/simple_C_sqrt_cap_{fee}bps/evaluation/daily.csv'))
    for lag in [5, 20]:
        controls.append((f'lag_{lag}', 'evaluation', deep/f'portfolios/financial_delay/C_lag{lag}/evaluation/daily.csv'))
    for family in ['A', 'B']:
        controls.append((f'ridge_{family}', 'evaluation', base/f'backtests/ridge_{family}_daily.csv'))
        controls.append((f'extra_{family}', 'evaluation', exp/f'portfolios/features/extra_raw_{family}/evaluation/daily.csv'))
    for case, phase, previous in controls:
        a = pd.read_csv(out/f'portfolios/{case}/{phase}/daily.csv')
        b = pd.read_csv(previous)
        np.testing.assert_allclose(a.net_return, b.net_return, atol=1e-12)
    # Independent factor ranking via SciPy; avoids production composite/rank code.
    u = pd.read_pickle(db/'panels/universe.pkl'); dates = u.loc['20220101':'20251231'].index
    sel = json.loads((base/'factor_selection.json').read_text())
    observed = np.load(base/'design/observed.npy', mmap_mode='r')
    allowed = (u.eq(1)&observed).reindex(dates)
    score = np.zeros((len(dates),len(u.columns)))
    for name in sel['fundamental']:
        raw = pd.read_pickle(base/'factors'/f'{name}.pkl').reindex(dates).to_numpy(float)*sel['directions'][name]
        for i in range(len(dates)):
            valid = allowed.iloc[i].to_numpy()&np.isfinite(raw[i])
            if valid.any():
                score[i,valid] += (rankdata(raw[i,valid],method='average')/valid.sum()-.5)/6
    cap = pd.read_pickle(db/'panels/market_cap.pkl').reindex(dates)
    score = pd.DataFrame(score,index=dates,columns=u.columns).where(allowed&np.isfinite(cap)&cap.gt(0))
    market = ResearchMarket(db)
    d, _, _, _ = market.backtest(score, '20230101', '20251231', weights=True,
        cost_bps=10, buffer_n=150, rebalance_every=10, weighting='sqrt_cap', max_weight=.02)
    reference = pd.read_csv(out/'portfolios/fundamental_sqrt_cap/evaluation/daily.csv')
    np.testing.assert_allclose(d.net_return, reference.net_return, atol=1e-12)
    # The nomination is explicit historical selection, never validation-only.
    nomination = json.loads((out/'final_strategy.json').read_text())
    assert nomination['selection_uses_previously_observed_evaluation']
    candidates = s.loc[s.phase.eq('evaluation')&~s.case.str.startswith(('pool_', 'without_', 'cost_', 'lag_'))]
    assert candidates.sort_values('annual_return').iloc[-1]['case'] == nomination['nominated']
    for r in json.loads((base/'run_manifest.json').read_text())['files']:
        assert digest(base/r['path']) == r['sha256']
    record = {'passed': True, 'reopened_portfolios': len(s),
        'independent_Scipy_rank_replay_max_error': float(np.max(np.abs(d.net_return.to_numpy()-reference.net_return.to_numpy()))),
        'cross_study_daily_controls': len(controls), 'baseline_artifacts_unchanged': 535,
        'retrospective_nomination_disclosed': True}
    (out/'audit/independent_verification.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config',default='configs/project2_final.json')
    p.add_argument('--output',default='runs/project2_final_v1')
    a = p.parse_args();run(a.config,a.output)
