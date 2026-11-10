# DSA5205 Project 2 — Team 34 Final Study

**Fundamental Signal Reconstruction and Portfolio Implementation in US Equities**

Members: Wan Gehong, Wang Tianyi, Wu Jiarui, Yan Tianao.

## Start here

- [Formal English report, 22 pages](reports/final/Group_34_Report.pdf): Abstract on page 1; contents on page 2.
- [Editable LaTeX](reports/final/Group_34_Report.tex).
- [Execution guide](docs/FINAL_STUDY.md).
- [Separate progress record](Project2_最终版进度.md).
- [Compact aggregate evidence](results/project2_final/README.md).

## Strategy and findings

Average six fixed-direction fundamental percentile scores; select Top100 with a rank-150 retention buffer; rebalance every ten sessions; use square-root-capitalization weights with a 2% formation target cap. Signal T close, execution T+1 close. Charge 10bps per dollar purchased or sold.

Observed 2023–2025 net CAGR: **23.34%**; Sharpe: **1.381**; maximum drawdown: **−20.78%**. SPY CAGR: 22.86%, with better Sharpe and drawdown. This is a retrospectively nominated candidate, not a blind-test winner. Stress tests and uncertainty do not establish robust outperformance.

The 0.47-point difference to SPY decomposes exactly into three matched comparisons (report §9): **+7.96** points of selection against the same universe at the same weights, **−6.70** points from holding that universe at square-root rather than capitalization weights, and **−0.78** points between the capitalization-weighted universe and SPY. The selection term is concentrated in 2024 and depends on the weighting scheme, and the candidate's 7.27% tracking error means about 8.4 points of annual excess would be needed over three years to reach two standard errors. The attribution is computed from stored daily returns after the evaluation period was inspected; it fits and selects nothing.

Data-vintage, membership and terminal-settlement limitations remain disclosed.

## Install and test

From this repository root, using Python 3.13:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest tests -q
```

Only relevant regression tests are included. The original workspace's 144-test suite is not claimed to be reproduced in full by this smaller repository. On macOS, importing XGBoost needs Homebrew's OpenMP runtime (`brew install libomp`); the final strategy itself does not fit XGBoost.

## Video

`video/slides.html` is the 30-slide animated deck (open in a browser; arrow keys to move, `n` toggles speaker notes). Slides cross-fade with a push, content rises in sequence, headline numbers count up, figures wipe in, and terminal output appears line by line. Every number on the slides is taken from `reports/final/tables/` and `reports/final/numbers.tex`; the figures are exported from `reports/final/figures/`.

`video/build_video.py` renders the deck into an MP4 with synthesized narration on macOS. The deck exposes `seek(slide, ms)`, which freezes every animation at an exact time, so the script screenshots each slide's animated opening frame by frame at 25 fps (Playwright), holds the last frame for the rest of the narration (`say`), and muxes with ffmpeg. Picture and voice are aligned by construction; no screen recording is involved.

```bash
python3 -m pip install -r video/requirements.txt && python3 -m playwright install chromium
cd video && python3 build_video.py --dry-run   # word counts and estimated length
cd video && python3 build_video.py             # writes video/Group_34_Video.mp4 (about 20 min)
```

The narration text is in each slide's `<aside class="notes">`; `docs/VIDEO_SCRIPT.md` has the same content as a speaker script for recording a human voice-over.

## Rebuild report figures without original data

```bash
PYTHONPATH=src .venv/bin/python scripts/build_final_report_assets.py
cd reports/final
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
```

The asset script also recomputes the return attribution and market-model diagnostics (`src/usq/project2/attribution.py`) from the stored daily returns, writes them to `results/project2_final/tables/`, and generates `reports/final/numbers.tex`, the macros behind every attribution number quoted in the report text. To print the attribution tables alone, run `PYTHONPATH=src .venv/bin/python -m usq.project2.attribution`.

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
