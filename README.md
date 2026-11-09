# DSA5205 Project 2 — Team 34 Final Study

**Fundamental Signal Reconstruction and Portfolio Implementation in US Equities**

Members: Wan Gehong, Wang Tianyi, Wu Jiarui, Yan Tianao.

## Start here

- [Formal English report, 20 pages](reports/final/Group_34_Report.pdf): Abstract on page 1; contents on page 2.
- [Editable LaTeX](reports/final/Group_34_Report.tex).
- [Execution guide](docs/FINAL_STUDY.md).
- [Separate progress record](Project2_最终版进度.md).
- [Compact aggregate evidence](results/project2_final/README.md).

## Strategy and findings

Average six fixed-direction fundamental percentile scores; select Top100 with a rank-150 retention buffer; rebalance every ten sessions; use square-root-capitalization weights with a 2% formation target cap. Signal T close, execution T+1 close. Charge 10bps per dollar purchased or sold.

Observed 2023–2025 net CAGR: **23.34%**; Sharpe: **1.381**; maximum drawdown: **−20.78%**. SPY CAGR: 22.86%, with better Sharpe and drawdown. This is a retrospectively nominated candidate, not a blind-test winner. Stress tests and uncertainty do not establish robust outperformance. Data-vintage, membership and terminal-settlement limitations remain disclosed.

## Install and test

From this repository root, using Python 3.13:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

Only relevant regression tests are included. The original workspace's 144-test suite is not claimed to be reproduced in full by this smaller repository. On macOS, importing XGBoost needs Homebrew's OpenMP runtime (`brew install libomp`); the final strategy itself does not fit XGBoost.

## Video

`video/slides.html` is the 28-slide presentation deck (open in a browser; arrow keys to move, `n` toggles speaker notes). Every number on the slides is taken from `reports/final/tables/` and the figures are exported from `reports/final/figures/`. `video/build_video.py` renders the deck into an MP4 with synthesized narration on macOS (headless Chrome + `say` + ffmpeg):

```bash
cd video && python3 build_video.py --dry-run   # word counts and estimated length
cd video && python3 build_video.py             # writes video/Group_34_Video.mp4
```

The narration text is in each slide's `<aside class="notes">`; `docs/VIDEO_SCRIPT.md` has the same content as a speaker script for recording a human voice-over.

## Rebuild report figures without original data

```bash
PYTHONPATH=src .venv/bin/python scripts/build_final_report_assets.py
cd reports/final
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
```

LaTeX is required for PDF compilation. Missing template packages are vendored with their original license notices. Report aggregates contain strategy returns and statistical summaries, not security-level source quotes, forecasts or holdings.

## Recompute the candidate with authorized data

Obtain the same authorized base snapshot from the team. It must contain the documented panels, metadata and checksums. Original data and historical experiment outputs are excluded.

```bash
PYTHONPATH=src .venv/bin/python -m usq.database.close_labels \
  --source data --output runs/snapshots/team34_nextclose10_v2
PYTHONPATH=src .venv/bin/python -m usq.project2.final_study \
  --standalone --output runs/project2_final_standalone_v1
```

The standalone path rebuilds signals and runs 14 portfolio/phase comparisons without historical factor caches or model predictions. See the guide for output protection and limitations. Optional full-study replay and its verifier require the team's private historical experiment directories; they are not prerequisites for the standalone strategy or report rebuild.

## Layout and provenance

`configs/`: frozen definitions. `src/usq/`: final entry and required shared modules. `tests/`: regression tests. `scripts/`: report assets and optional full-study verification. `results/project2_final/`: aggregate evidence. `reports/final/`: PDF, LaTeX, figures and tables. `docs/`: execution guide.

This curated version continues the [original team repository](https://github.com/jiarui22/dsa5205_project2). Historical local experiments remain preserved separately. No new license grant is asserted for original team code, institutional data, or the supplied template.
