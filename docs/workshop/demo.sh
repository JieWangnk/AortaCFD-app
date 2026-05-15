#!/bin/bash
# Workshop demo — full Block A→B→C→D pipeline on 10 synthetic aortas.
#
# Run this from the AortaCFD-app root with OpenFOAM 12 sourced and the
# venv activated:
#
#   source venv/bin/activate
#   source /opt/openfoam12/etc/bashrc
#   bash docs/workshop/demo.sh
#
# Total wall-clock: ~10 min on an 8-core laptop (1:35 per case, 2 workers).
#
# Outputs:
#   /tmp/gen_severity/                 (Block A — 10 STL folders)
#   cases_input/sev_*/                 (Block B — packaged cases)
#   output/sev_*/                      (Block C — solver results)
#   output/cohort_comparison.csv       (Block D — aggregated QoIs)

set -euo pipefail

# Activate venv if not already active (so the script is fire-and-forget)
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

GEOMGEN=${GEOMGEN:-$HOME/GitHub/aortacfd-geomgen}
LIMIT=${LIMIT:-}                       # set LIMIT=3 to test with 3 cases first
EXTRA_LIMIT_ARG=""
[ -n "$LIMIT" ] && EXTRA_LIMIT_ARG="--limit $LIMIT"

echo "━━━ Block A: Generate 10 synthetic aortas (severity 0→0.9) ━━━"
time python "$GEOMGEN/cli.py" \
    --spec "$GEOMGEN/specs/sweep_severity.json" \
    --output /tmp/gen_severity \
    $EXTRA_LIMIT_ARG

echo
echo "━━━ Block B: Stamp config.json on each case ━━━"
# Clean stale runs from any earlier demo
rm -rf cases_input/sev_*
rm -rf output/sev_*

# Package into a flat layout where every sev_NNN/ is a direct child of cases_input/
python -m scripts.package_cases /tmp/gen_severity \
    --config-template examples/templates/config_workshop_quick.json \
    --output /tmp/packaged_severity

# Move each packaged case into cases_input/ as a direct child so run_patient.py can find it
for d in /tmp/packaged_severity/sev_*; do
    [ -d "$d" ] && mv "$d" cases_input/
done

echo
echo "━━━ Block C: Run 10 cases locally with 2 workers ━━━"
CASES=$(ls -d cases_input/sev_* | xargs -n1 basename | tr '\n' ' ')
echo "Cases: $CASES"
# Note: --quick is a run_patient.py flag, not a run_batch.py flag. The
# template config_workshop_quick.json already bakes in the quick settings
# (8 cpd, 1 cycle, 0.2s endTime, 3 outer correctors). So no --quick needed.
time python run_batch.py --cases $CASES --workers 2

echo
echo "━━━ Block D: Aggregate cohort QoIs ━━━"
python -m scripts.compare_cohort output/

echo
echo "━━━ Done. Cohort CSV: ━━━"
head -1 output/cohort_comparison.csv
echo "..."
wc -l output/cohort_comparison.csv

echo
echo "━━━ Plotting QoI vs severity ━━━"
python docs/workshop/plot_severity_sweep.py

echo
echo "Open in ParaView:"
echo "  paraview cases_input/sev_005/wall_aorta.stl"
echo "Or visualise the solver output:"
echo "  paraview output/sev_005/run_*/openfoam/sev_005.foam"
echo
echo "Pressure-drop-vs-severity plot:"
echo "  xdg-open output/severity_sweep.png   # or any image viewer"
