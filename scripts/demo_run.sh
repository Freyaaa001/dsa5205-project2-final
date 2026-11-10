#!/usr/bin/env bash
# Paced end-to-end run for the project video. Every step prints the exact command
# before running it, so a screen recording of this script is the demonstration.
#
#   bash scripts/demo_run.sh              # with the authorized data snapshot
#   bash scripts/demo_run.sh aggregates   # without data: tests, report assets, PDF
#
# PAUSE=<seconds> sets the pause after each heading (default 2).
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-data}"
PAUSE="${PAUSE:-2}"
SOURCE="${SOURCE:-data}"
SNAPSHOT="runs/snapshots/team34_nextclose10_v2"     # the path configs/project2_final.json reads
STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="runs/demo_video_${STAMP}"
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; else PY="python3"; fi
export PYTHONPATH=src

heading() {
  printf '\n\033[1;36m━━━ %s ━━━\033[0m\n' "$1"
  sleep "$PAUSE"
}

show() {    # print the command, run it, report how long it took
  local started=$SECONDS
  if [ "$1" = "$PY" ]; then printf '\033[1;33m$ PYTHONPATH=src %s\033[0m\n' "$*"; else printf '\033[1;33m$ %s\033[0m\n' "$*"; fi
  sleep 1
  "$@"
  printf '\033[2m(%ss)\033[0m\n' "$((SECONDS - started))"
}

case "$MODE" in
  data|aggregates) ;;
  *) echo "usage: bash scripts/demo_run.sh [data|aggregates]" >&2; exit 2 ;;
esac

heading "0 · Environment"
show "$PY" --version
show grep -E "^(numpy|pandas|scipy|scikit-learn|xgboost)" requirements.txt
show git log --oneline -1

if [ "$MODE" = "data" ]; then
  if [ ! -d "$SOURCE" ] && [ ! -d "$SNAPSHOT" ]; then
    echo "Neither $SOURCE/ nor $SNAPSHOT/ exists. Run this on the machine that holds the authorized snapshot," >&2
    echo "or use: bash scripts/demo_run.sh aggregates" >&2
    exit 1
  fi

  heading "1 · Data build: aligned daily panels and ten-interval labels"
  if [ -d "$SOURCE" ]; then
    # close_labels refuses to overwrite, so an existing frozen snapshot is never touched.
    if [ -d "$SNAPSHOT" ]; then BUILD="runs/snapshots/demo_${STAMP}"; else BUILD="$SNAPSHOT"; fi
    show "$PY" -m usq.database.close_labels --source "$SOURCE" --output "$BUILD"
  else
    echo "$SOURCE/ is not on this machine; the frozen snapshot $SNAPSHOT is used as built."
  fi

  heading "2 · Signals → validation 2022 → out-of-sample 2023-2025, net of costs"
  show "$PY" -m usq.project2.final_study --standalone --output "$OUTPUT"

  heading "3 · Net results and reconciliation with the shipped ledgers"
  show "$PY" scripts/show_summary.py "$OUTPUT"
fi

heading "4 · Regression tests"
show "$PY" -m pytest tests -q

heading "5 · Report tables, figures and return attribution from the stored ledgers"
show "$PY" scripts/build_final_report_assets.py
show cat reports/final/tables/attribution.tex

if command -v pdflatex >/dev/null 2>&1; then
  heading "6 · Compile the report"
  printf '\033[1;33m$ cd reports/final && TEXINPUTS=./tex-support: pdflatex Group_34_Report.tex   (twice)\033[0m\n'
  (
    cd reports/final
    for pass in 1 2; do
      TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex >/dev/null
    done
    grep 'Output written on' Group_34_Report.log
  )
else
  echo "pdflatex not found; skipping the PDF step."
fi

heading "Done"
[ "$MODE" = "data" ] && echo "Strategy output: $OUTPUT"
echo "Regenerated report files can be discarded with: git checkout -- reports/final"
