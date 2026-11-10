"""Print the headline rows of a final-study output and reconcile them with the shipped aggregates."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

CASES = ['fundamental_sqrt_cap', 'fundamental_cap', 'fundamental_equal',
         'pool_sqrt_cap', 'pool_cap', 'pool_equal', 'cost_20', 'cost_30']
COLUMNS = ['case', 'phase', 'days', 'annual_return', 'annual_volatility', 'sharpe',
           'max_drawdown', 'mean_daily_turnover', 'spy_annual_return', 'cost_bps']


def run(output, reference):
    output, reference = Path(output), Path(reference)
    summary = pd.read_csv(output/'portfolio_summary.csv')
    rows = summary.loc[summary.case.isin(CASES), [c for c in COLUMNS if c in summary.columns]]
    rows = rows.assign(order=rows.case.map(CASES.index)).sort_values(['phase', 'order'], ascending=[False, True])
    print(f'{output}/portfolio_summary.csv  ({len(summary)} portfolio/phase rows)\n')
    print(rows.drop(columns='order').round(4).to_string(index=False))
    audit = output/'audit/verification.json'
    if audit.exists():
        print(f'\n{audit}:\n{json.dumps(json.loads(audit.read_text()), indent=2)}')
    if output.resolve() == reference.resolve():
        return
    print(f'\nReconciliation with the shipped aggregates in {reference}:')
    for phase in ['validation', 'evaluation']:
        path = Path('portfolios')/'fundamental_sqrt_cap'/phase/'daily.csv'
        new, old = pd.read_csv(output/path), pd.read_csv(reference/path)
        if len(new) != len(old):
            raise SystemExit(f'{phase}: {len(new)} sessions here, {len(old)} in the shipped ledger')
        gap = float(np.max(np.abs(new.net_return.to_numpy()-old.net_return.to_numpy())))
        print(f'  candidate {phase:10s} {len(new)} sessions, max |daily net return difference| = {gap:.2e}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--reference', default='results/project2_final')
    arguments = parser.parse_args()
    run(arguments.output, arguments.reference)
