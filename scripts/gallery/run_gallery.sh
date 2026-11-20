#!/usr/bin/env bash
# Run the OpenCardioFlow gallery cases one at a time on 4 cores, then export
# each finished run as a web bundle. Resumable: a run with a .done marker is
# skipped. Start it as a user service so a desktop crash does not kill it:
#
#   systemd-run --user --unit=ocf-gallery --collect \
#       --working-directory="$PWD" bash scripts/gallery/run_gallery.sh
#
# Markers and logs live in output/_gallery/.
set -o pipefail
cd "$(dirname "$0")/../.." || exit 1
ROOT=$PWD
G=$ROOT/output/_gallery
mkdir -p "$G/bundles" "$G/logs"
LOG=$G/batch.log
# No 'postprocess' step: its ParaView image stage (pvbatch) crashed and hung on 19 Nov 2026;
# the web figures are rendered later from the fields. 'hemodynamics' still writes the QoIs.
STEPS=case,mesh,boundary,solver,reconstruct,hemodynamics

# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
# shellcheck disable=SC1091
source /opt/openfoam12/etc/bashrc >/dev/null 2>&1
export OMP_NUM_THREADS=1

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

log "batch start pid $$"
# The run list is read on file descriptor 3 and every child gets /dev/null as stdin:
# mpirun forwards stdin to rank 0 and would otherwise swallow the rest of the list
# (that ended the batch after one run on 20 Nov 2026).
while read -r -u 3 CASE RUN CFG; do
    [ -z "$CASE" ] && continue
    TAG="${CASE}__${RUN}"
    if [ -f "$G/$TAG.done" ]; then log "skip $TAG (done)"; continue; fi
    rm -f "$G/$TAG.failed"
    log "start $TAG"
    t0=$(date +%s)
    timeout -k 60 12h nice -n 10 python run_patient.py "$CASE" --config "$CFG" --steps "$STEPS" --run-name "$RUN" \
        < /dev/null > "$G/logs/$TAG.log" 2>&1
    rc=$?
    dt=$(( $(date +%s) - t0 ))
    if [ $rc -ne 0 ]; then
        log "FAILED $TAG rc=$rc after ${dt}s"
        touch "$G/$TAG.failed"
        continue
    fi
    cells=$(grep -m1 -oE 'cells:\s+[0-9]+' "$ROOT/output/$CASE/$RUN/openfoam/logs/log.checkMesh" 2>/dev/null | grep -oE '[0-9]+')
    log "solved $TAG in ${dt}s, cells ${cells:-?}"
    grep -hE 'CHECK|FAIL|RISK|WARN' "$ROOT/output/$CASE/$RUN/reports/"*.txt 2>/dev/null | sort -u | head -20 | sed "s/^/    flag: /" | tee -a "$LOG"
    nice -n 10 python -m aortacfd_lib.web_export "output/$CASE/$RUN" -o "$G/bundles/$TAG" \
        < /dev/null > "$G/logs/$TAG.export.log" 2>&1 \
        && log "exported $TAG" || log "EXPORT FAILED $TAG (see logs/$TAG.export.log)"
    touch "$G/$TAG.done"
done 3< "$ROOT/scripts/gallery/runs.txt"
log "batch end"
touch "$G/ALL_DONE"
