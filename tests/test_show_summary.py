"""The demo's result printer must reconcile a replay with the shipped ledgers."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'results/project2_final'


def replay_copy(tmp_path):
    shutil.copy(RESULTS/'portfolio_summary.csv', tmp_path)
    shutil.copytree(RESULTS/'portfolios/fundamental_sqrt_cap', tmp_path/'portfolios/fundamental_sqrt_cap')
    return tmp_path


def show(output):
    return subprocess.run([sys.executable, str(ROOT/'scripts/show_summary.py'), str(output),
                           '--reference', str(RESULTS)], capture_output=True, text=True, cwd=ROOT)


def test_identical_replay_reconciles_to_zero(tmp_path):
    done = show(replay_copy(tmp_path))
    assert done.returncode == 0, done.stderr
    assert 'fundamental_sqrt_cap evaluation   752' in done.stdout
    assert done.stdout.count('max |daily net return difference| = 0.00e+00') == 2


def test_a_shifted_or_truncated_replay_is_reported(tmp_path):
    out = replay_copy(tmp_path)
    ledger = out/'portfolios/fundamental_sqrt_cap/evaluation/daily.csv'
    lines = ledger.read_text().splitlines()
    ledger.write_text('\n'.join(lines[:-1])+'\n')
    done = show(out)
    assert done.returncode != 0 and '751 sessions here, 752 in the shipped ledger' in done.stderr
