# Final-study aggregate evidence

These are compact, strategy-level outputs supporting the final manuscript. No original security-level prices, forecasts, holdings, or credentials are included. `protocol.json` retains the historical input pointers for provenance; the report asset builder reads the aggregates in this directory and does not need those original paths to exist.

- `portfolio_summary.csv`: 38 representative portfolio/phase combinations.
- `portfolios/*/*/daily.csv`: daily strategy-level ledgers, including costs and aligned SPY returns.
- `tables/`: factor summaries, screening records, common training-window counts, annual returns, paired intervals, correlation, universe counts, and style/concentration summaries. `attribution.csv`, `attribution_annual.csv`, `selection_by_weighting.csv` and `capm.csv` are written by `usq.project2.attribution` from the daily ledgers above: the selection/weighting/universe attribution of the candidate's return difference to SPY and market-model diagnostics.
- `final_strategy.json`: explicitly retrospective nomination of the six-fundamental square-root-capitalization candidate.

From the repository root:

```bash
PYTHONPATH=src python scripts/build_final_report_assets.py
```

For actual signal/backtest reproduction from the authorized source snapshot, see `docs/FINAL_STUDY.md`; aggregate evidence alone cannot independently reconstruct financial inputs or certify their historical provenance.
