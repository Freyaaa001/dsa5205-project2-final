# Team 34 — Project 2 Video Script (target 20 min, range 15–25)

Rubric coverage (10 points): (1) end-to-end run — data → fit → validation → out-of-sample with costs — with time-order integrity and leakage controls; (2) model story, overfitting control, rule from prediction to position; (3) required out-of-sample figures, results, what we learned.

All numbers below come from `reports/final/tables/*.tex` and the report PDF. Do not quote any other number. 中文为给讲者的提示，不要念出来。

Suggested split: four segments of roughly five minutes, one per member. Record screen + voice (Zoom "record to computer", QuickTime, or OBS). Upload as unlisted YouTube or OneDrive and test the link in a private browser window before pasting it into Canvas.

---

## 0. Title (0:00–0:45) — Speaker A

Screen: report page 1.

> Hello. We are Team 34. Our project is "Fundamental Signal Reconstruction and Portfolio Implementation in US Equities". In the next twenty minutes we walk through the full pipeline: the data and timing rules, the signals, how we validated and controlled overfitting, how a score becomes a position, a live run of the code, and the out-of-sample results with costs. We end with what worked, what did not, and what we learned.

中文提示：报到团队名和四人姓名（名单补齐后念全名）。不要在这里报收益数字。

## 1. Markets, timing, benchmark (0:45–3:30) — Speaker A

Screen: report §2, Figure 1 (`figures/universe.pdf`).

> **Assets.** We trade a supplied US common-equity panel built from CRSP-style prices and Compustat-style financial statements, aligned to the NYSE calendar, in US dollars. The panel covers 2014 to 2025. On any given day about two thousand names are eligible — the median is 2,086 — even though the union of identifiers over the whole period is 4,366. Figure 1 shows daily membership. We flag up front that the historical membership rules of this extract are not fully documented, so every result is conditional on the supplied pool.
>
> **Frequency and timing.** Decisions are daily. A signal is computed from information available at the close of session T. We execute at the close of T+1, and the new holding earns its first close-to-close return on T+2. So a closing price is never used to trade at that same close.
>
> **Benchmark.** The investable benchmark is SPY, buy-and-hold, using the supplied adjusted total-return close. We also build three same-universe allocation benchmarks — equal-weight, square-root-cap and cap-weighted portfolios of the whole eligible pool — rebalanced every ten sessions and charged the same costs. These isolate the effect of allocation from the effect of our signal.
>
> **Costs.** Ten basis points per dollar traded, charged on both buys and sells, with 20 and 30 bps as stress cases.

中文提示：强调「T 收盘出信号、T+1 收盘成交、T+2 才有第一段持仓收益」，这是评分表里 decision vs execution 的核心。

## 2. Labels and features (3:30–7:00) — Speaker B

Screen: report §2.3 equation (1), Table 2 (fundamental definitions), Figure 2 (`figures/correlation.pdf`), Table 3.

> **Label.** The supervised target is the ten-interval return from the close of T+1 to the close of T+11, in exchange sessions. Equation (1). The horizon H is ten close-to-close intervals, aligned to our execution at T+1. The last eleven signal dates in the sample are censored because their labels have not matured. Labels are only used for research and screening; portfolio P&L comes from actual held weights and daily marks, never from treating overlapping ten-day labels as daily returns.
>
> **Six fundamental signals.** Table 2. Four of them are residuals: for example F1 regresses signed-log net income on signed-log market cap across the cross-section each day and keeps the residual — it measures earnings strength conditional on size, rather than a raw ratio. F5 is free-cash-flow yield over an enterprise-value proxy. F6 is a seasonal earnings surprise, normalised by the last market cap strictly before the release date.
>
> **Fixed signs.** Each signal's direction was fixed using average RankIC on 2015–2018 only. Two signs are negative — F2 book equity and F3 sales — so the composite does not simply buy "more of everything". Signs were never revisited after 2018.
>
> **Price–volume signals.** We implemented 36 formulaic alphas from Kakushadze's list. Direction on 2015–2018, stability screen on 2019–2021 — signed RankIC at least 0.01, coverage at least 50%, positive in at least two of three years — and a 0.8 rank-correlation redundancy cut. Three survive: WQ040, WQ019, WQ026.
>
> **Leakage controls.** Three rules. First, all ranks are cross-sectional within the same date, so scaling uses no future moments. Second, every financial field has a mapped availability date, and the earnings surprise requires all twelve prior quarters to be available before the release. Third, we later stress this by delaying every availability date by five and twenty sessions and rebuilding the signals from scratch. Missing values become a neutral zero contribution rather than dropping the stock.

中文提示：如果时间紧，Table 3 的 RankIC 数字只需说「单因子 RankIC 都很小，这是预期之内的」，不要逐个念。

## 3. Data split, models, validation, overfitting (7:00–10:30) — Speaker B

Screen: report §2.3 last paragraphs, Table 1 (training windows), §4 Table 4 (grids).

> **Split.** 2015–2018 fixes factor directions. 2019–2021 checks stability and redundancy. 2022 is the validation year, used for hyper-parameters and trading rules. 2023–2025 is the evaluation period. Learned models are refit every half-year on an expanding window from 2015, and a training row is admissible only if its label has fully matured before the forecast origin — T+11 strictly earlier than τ. Table 1 shows the six windows; the last label end is always before the next forecast half begins.
>
> **Economic story.** Accounting information is slow-moving and we expected it to complement fast price–volume signals. We tested that in two ways: adding fundamentals to a learned forecast — group A is price–volume only, B adds the six fundamentals — and using the fundamentals directly as a rank composite.
>
> **Models and grids.** Ridge, Lasso, and shallow XGBoost, each on A and B with identical dates, rows, targets and seeds. The grids were tiny and declared in advance — Table 4: two ridge penalties, two lasso penalties, tree depth two or three. The selection rule was one number: 2022 daily RankIC on group A. We tried six model-group pairs plus the grids in Table 4; that is the entire search.
>
> **Overfitting control.** Shrinkage in every learner, only nine inputs, depth-two trees with a minimum child weight of 100, fixed seed 5205, and no re-tuning after 2022. For the final composite there is no fitted return model at all — six fixed-sign ranks averaged — so there is almost nothing to overfit in the forecasting step.
>
> **Honesty about selection.** The square-root-cap weighting of the final candidate was nominated after we had seen the 2023–2025 comparisons. We say so explicitly in the report: it is a retrospective nomination among reported alternatives, not a blind-test winner. In 2022 the cap-weighted variant actually did slightly better.

中文提示：最后一段必须讲，这是报告反复强调的诚实声明，评分看的是 process。

## 4. From score to position (10:30–12:30) — Speaker C

Screen: report §5 equation (3), paragraphs on buffer and weights, equation (4).

> The composite score S is the average of six signed percentile ranks, centred at zero, with missing signals contributing zero and the denominator fixed at six. Equation (3).
>
> On every tenth session we form targets. Names already held are kept if their rank is still within the top 150; remaining slots are filled in score order down to about 100 names. The 150 buffer is what keeps turnover under one percent per day.
>
> Inside the selected set, weights are proportional to the square root of market cap, with a 2% target cap per name applied by water-filling; the residual stays in cash. Long-only, no leverage, cash earns zero.
>
> Accounting, equation (4): gross return is beginning-of-period weights times returns; cost is b basis points times absolute traded notional, both sides; net is the difference. We start from cash, enter at the first scheduled next-close trade, and liquidate at the end, so the compound return includes entry and exit costs. Unfillable buys stay in cash and unsellable names stay held — the ledger never substitutes a name using a future quote.

## 5. Live end-to-end run (12:30–15:30) — Speaker C

Screen: terminal at the repository root. Have the commands pre-typed; run them in order. If the authorised data snapshot is on this machine, use block (a); otherwise use block (b) and say that the raw panel cannot be redistributed.

**(a) With the data snapshot** (shows data build → signals → portfolio → costs):

```bash
PYTHONPATH=src .venv/bin/python -m usq.database.close_labels --source data --output runs/snapshots/team34_nextclose10_v2
PYTHONPATH=src .venv/bin/python -m usq.project2.final_study --standalone --output runs/demo_video
head -3 runs/demo_video/portfolio_summary.csv
```

> This first command builds the aligned daily panel and the ten-interval labels from the raw snapshot. The second rebuilds all six fundamentals from the financial statements, forms the composite, replays the buffered selection and the sqrt-cap allocation through the cost ledger, and writes fourteen portfolio–phase combinations. Nothing is fitted here; the run is deterministic and the tie-break seed is 5205. The summary row for `fundamental_sqrt_cap`, evaluation phase, shows annual return 0.2334 and Sharpe 1.381 — the same numbers as the report.

**(b) Without the data** (shows tests → figures → report, from the included aggregates):

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q
PYTHONPATH=src .venv/bin/python scripts/build_final_report_assets.py
cd reports/final && TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode Group_34_Report.tex
```

> The tests cover the label protocol, the buffered selection, the ledger accounting and the final-study entry. The asset script regenerates every table and figure in the report from `results/project2_final/` — the report contains no hand-typed result numbers. Then LaTeX compiles the twenty-page PDF.

中文提示：录之前先跑一遍，确认 pytest 全绿、PDF 页数为 20。终端字体调大。不要在镜头里展示 data/ 目录的个股文件。

## 6. Out-of-sample results (15:30–19:00) — Speaker D

Screen in order: Table 9 (final comparison), Figure 4 (`wealth_drawdown.pdf`), Table 10 + Figure 5 (annual), Table 8 (pool), Table 12 + Figure 7 (stress), Table 13 + Figure 8 (intervals).

> **Headline.** Over 2023–2025, net of 10 bps, the candidate compounds at 23.34% a year, volatility 16.14%, Sharpe 1.381, maximum drawdown −20.78%. SPY over the same window: 22.86%, Sharpe 1.419, drawdown −18.76%. So we beat SPY on return by about half a point, and lose to it on Sharpe and drawdown. Figure 4 shows the wealth and drawdown paths.
>
> **Year by year.** Table 10: minus 6.2 points in 2023, plus 8.8 in 2024, minus 0.7 in 2025. The edge is not stable across years.
>
> **Allocation explains most of the gap.** Table 8: the same pool with no signal at all earns 12.25% equal-weighted, 15.38% sqrt-cap, and 22.08% cap-weighted. Our signal adds 1.26 points over the cap-weighted pool. Equal-weight model portfolios should not be judged only by their distance to a cap-weighted ETF.
>
> **Learned models.** Adding fundamentals to a learner moved Ridge from 8.25% to 8.51% and XGBoost from 9.49% to 9.83% — tiny. Lasso A and B were identical because every factor coefficient was zero. That is why the final candidate is the simple composite rather than a learned forecast.
>
> **Stress.** Table 12: at 20 bps the candidate drops to 22.83%, already below SPY; at 30 bps, 22.32%. A twenty-session delay in financial availability gives 21.77%.
>
> **Ablation.** Removing any one of the six signals lowers 2023–2025 CAGR, by 2.3 to 5.0 points. But in 2022, removing F2 would have helped by over ten points — so we do not claim stable stand-alone alpha for each factor, and we did not use these results to change the set.
>
> **Fusion.** Mixing in a ridge price score with weight 0.25 — chosen on 2022 — lowered the 2023–2025 CAGR to 20.30% and raised daily turnover from 0.82% to 4.16%. More information did not help.
>
> **Uncertainty.** Paired circular block bootstrap, 2,000 resamples, seed 5205. Table 13: the CAGR difference to SPY is +0.47 points with a 95% interval from −8.3 to +11.7. Every comparator's interval includes zero.

中文提示：这一段数字最多，照表念，不要即兴换算。

## 7. What worked, what did not, what we learned (19:00–21:00) — Speaker D

Screen: report §12 and §13.

> **What worked.** The pipeline: strict next-close execution, matured-label purging, fixed signs from 2015–2018, one pre-declared selection rule, and a cost ledger that reconciles to the wealth path to the cent. The composite's turnover of under one percent per day makes it cheap to run.
>
> **What did not.** Adding fundamentals to learned forecasts did not help. Score fusion looked good in 2022 and failed afterwards. The return advantage over SPY is small, sign-flipping across years, and statistically indistinguishable from zero.
>
> **What we learned.** First, allocation and the opportunity set explain most of a strategy's distance to an ETF; compare against a matched-universe cap-weighted benchmark before crediting the signal. Second, lower turnover is not evidence of better forecasts. Third, a validation year can prefer the wrong thing — fusion — so an untouched holdout matters more than a good validation score. Fourth, our data are latest financial vintages, not point-in-time, and membership lineage is incomplete, so we report the result as a transparent retrospective candidate, not a deployable alpha.

## 8. Reproducibility and contributions (21:00–22:00) — Speaker A

Screen: README.md, then the roster paragraph in Appendix A.

> The repository has a README with the exact commands we just ran, pinned requirements, fixed seeds and relative paths. Raw data are not redistributed; the aggregate ledgers needed to rebuild every figure are included. Contributions: [each member states their part in one sentence].

中文提示：分工一句话一人，与报告附录的 contribution note 完全一致。

---

## Pre-recording checklist

- [ ] Roster, student IDs and contribution note filled in the report and in this script.
- [ ] `pytest` green and PDF rebuilt on the recording machine.
- [ ] Terminal font ≥ 18 pt; PDF zoomed so tables are readable at 1080p.
- [ ] Dry run timed: total between 15 and 25 minutes.
- [ ] Link tested while logged out; download allowed.
