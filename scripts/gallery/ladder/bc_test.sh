#!/bin/bash
# Restart test of the outlet backflow damping on the fine Ladder 3 mesh.
# Usage: bc_test.sh <name> <betaT> <betaN> [start_time=0.432] [end_time=0.56]
# Copies the decomposed case at <start_time> from the stalled fine run, sets the damping factors in every
# processor's U file, runs foamRun on 4 cores and stops it if the time step collapses below 1e-7 s.
set +u
NAME=$1; BT=$2; BN=$3; T0=${4:-0.432}; T1=${5:-0.56}
APP=/home/mchi4jw4/GitHub/AortaCFD-app
SRC=$APP/output/ladder_L3/gallery_fine_span26/openfoam
DST=$APP/output/_ladder/bc_tests/$NAME
if [ -e "$DST" ]; then echo "exists: $DST"; exit 1; fi
mkdir -p "$DST"
cp -r "$SRC/system" "$SRC/constant" "$DST/"
for p in 0 1 2 3; do
    mkdir -p "$DST/processor$p"
    cp -r "$SRC/processor$p/constant" "$SRC/processor$p/$T0" "$DST/processor$p/"
    sed -i -E "s/^(\s*betaT\s+)[0-9.eE+-]+;/\1$BT;/; s/^(\s*betaN\s+)[0-9.eE+-]+;/\1$BN;/" "$DST/processor$p/$T0/U"
done
grep -ahE "^\s*beta[TN]" "$DST/processor1/$T0/U"
sed -i -E "s/^(startFrom\s+).*/\1startTime;/; s/^(startTime\s+).*/\1$T0;/; s/^(endTime\s+).*/\1$T1;/" "$DST/system/controlDict"
grep -E "^(startFrom|startTime|endTime)" "$DST/system/controlDict"
cd "$DST" || exit 1
source /opt/openfoam12/etc/bashrc
mpirun -np 4 foamRun -parallel > log.solver 2>&1 &
PID=$!
echo "started pid $PID at $(date '+%H:%M:%S')"
while kill -0 $PID 2>/dev/null; do
    sleep 30
    t=$(grep -E '^Time = ' log.solver | tail -1 | awk '{print $3}')
    dt=$(grep -E '^deltaT = ' log.solver | tail -1 | awk '{print $3}')
    if [ -n "$dt" ] && awk -v d="$dt" 'BEGIN{exit !(d < 1e-7)}'; then
        echo "COLLAPSE at Time $t deltaT $dt $(date '+%H:%M:%S')"; kill $PID; sleep 2; pkill -P $PID 2>/dev/null; exit 2
    fi
done
wait $PID; rc=$?
echo "finished rc=$rc at $(date '+%H:%M:%S'); last Time $(grep -E '^Time = ' log.solver | tail -1); $(grep ExecutionTime log.solver | tail -1)"
awk '/^Time = /{t=$3+0} /^deltaT = /{dt=$3+0; if(m==0||dt<m){m=dt;tm=t}} END{printf "min deltaT %g at t=%g\n",m,tm}' log.solver
grep -E "^(End|FOAM FATAL)" log.solver | head -n 3
exit $rc
