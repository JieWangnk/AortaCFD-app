#!/bin/bash
# Waiter for the complexity-ladder batch (user service ocf-ladder). Polls every 10 min and exits when:
#   0  ALL_DONE marker written (prints the batch log summary)
#   2  a stall: the solver's Time has not advanced since the last poll, or deltaT is below 1e-8
#      (dt-collapse); writes STALL in the batch dir and stops the service
#   3  the service is no longer active and there is no ALL_DONE (the batch died)
# Failed runs do not stop the batch (run_gallery.sh moves on); they are listed at the end.
APP=${APP:-$(cd "$(dirname "$0")/../../.." && pwd)}
G=$APP/output/_ladder
UNIT=ocf-ladder
last_tag=""; last_time=""
while true; do
    if [ -f "$G/ALL_DONE" ]; then
        echo "ALL_DONE $(date '+%H:%M')"; grep -E 'solved|FAILED|flag:' "$G/batch.log"; ls "$G"/*.failed 2>/dev/null; exit 0
    fi
    if ! systemctl --user is-active --quiet "$UNIT"; then
        echo "SERVICE INACTIVE without ALL_DONE $(date '+%H:%M')"; tail -5 "$G/batch.log"; exit 3
    fi
    tag=$(grep -oE 'start [A-Za-z0-9_]+' "$G/batch.log" | tail -1 | cut -d' ' -f2)
    if [ -n "$tag" ]; then
        case=${tag%%__*}; run=${tag#*__}
        log=$APP/output/$case/$run/openfoam/logs/log.solver
        if [ -f "$log" ]; then
            t=$(grep -E '^Time = ' "$log" | tail -1 | awk '{print $3}')
            dt=$(grep -E '^deltaT = ' "$log" | tail -1 | awk '{print $3}')
            if [ "$tag" = "$last_tag" ] && [ -n "$t" ] && [ "$t" = "$last_time" ]; then
                echo "STALL $tag: Time stuck at $t $(date '+%H:%M')"; touch "$G/STALL"; systemctl --user stop "$UNIT"; exit 2
            fi
            if [ -n "$dt" ] && awk -v d="$dt" 'BEGIN{exit !(d < 1e-8)}'; then
                echo "STALL $tag: deltaT collapsed to $dt at Time $t $(date '+%H:%M')"; touch "$G/STALL"; systemctl --user stop "$UNIT"; exit 2
            fi
            last_tag=$tag; last_time=$t
        fi
    fi
    sleep 600
done
