#!/usr/bin/env bash
# run.sh - runs the experiments and writes results.csv
# Usage:  ./run.sh            (full run, roughly 20-30 min)
#         QUICK=1 ./run.sh    (fast smoke test, a few minutes)
# Environment:
#   ONLY=intensity,reuse,threads,real   run only these experiments (default: all)
#   OUTDIR=<dir>     where outputs go (default: this directory), e.g. OUTDIR=data/$(hostname)
#   TAG=<name>       suffix for output files, e.g. TAG=run2 -> results_run2.csv
#   COOLDOWN=<f>     idle time after each run, as a multiple of its wall time (default 1.5;
#                    keeps the running-average package power below the long-term power
#                    limit PL1 so timed runs are not throttled; 0 disables)
#   MEASURE_Q=0      don't measure DRAM traffic of the real kernels with perf; use formulas
# Outputs (in OUTDIR, with _TAG suffix if set):
#   results.csv       Section-5 format (the only file analyze.py needs)
#   machine_info.txt  lscpu + derived core/cache numbers
#   idle_power.txt    idle package power
#   q_measured.csv    Exp 4: analytic vs perf-measured DRAM bytes per rep
#   run_log.txt       per-run diagnostics from stderr (load imbalance, psys, Q method)
set -euo pipefail
cd "$(dirname "$0")"

gcc -O3 -march=native -fopenmp -o bench bench.c
gcc -O3 -march=native -fopenmp -o kernels kernels.c -lm

ONLY=${ONLY:-intensity,reuse,threads,real}
want() { [[ ",$ONLY," == *",$1,"* ]]; }
OUTDIR=${OUTDIR:-.}; mkdir -p "$OUTDIR"
SUF=${TAG:+_$TAG}
OUT=$OUTDIR/results$SUF.csv
LOGF=$OUTDIR/run_log$SUF.txt
COOLDOWN=${COOLDOWN:-1.5}

# ---------- machine info ----------
PHYS=$(lscpu -p=CORE,SOCKET | grep -v '^#' | sort -u | wc -l)   # physical cores
LOG=$(nproc)                                                    # logical CPUs (with SMT)
cache_kb() {  # total size of cache level $1 (data/unified) over all instances, in KB
  lscpu -B -C=LEVEL,TYPE,ALL-SIZE | awk -v l=$1 '$1==l && $2!="Instruction" {print int($3/1024); f=1} END{if(!f) print 0}'; }
L1=$(cache_kb 1); L2=$(cache_kb 2); L3=$(cache_kb 3)
{ lscpu; echo; lscpu -e; echo; cat /proc/meminfo | head -3; } > "$OUTDIR/machine_info$SUF.txt"
echo "physical_cores=$PHYS logical=$LOG L1_total=${L1}K L2_total=${L2}K L3_total=${L3}K" | tee -a "$OUTDIR/machine_info$SUF.txt"

export OMP_PROC_BIND=close OMP_PLACES=cores
REPEAT=3; MINS=1.0
KS="1 2 4 8 16 32 64 128 256 512"
DRAM_N=$(( 64 * 1024 * 1024 ))          # 64M doubles = 512 MB (well beyond L3)
[ $(( L3 * 1024 * 4 / 8 )) -gt $DRAM_N ] && DRAM_N=$(( L3 * 1024 * 4 / 8 ))   # at least 4x L3
TRIAD_N=$((32*1024*1024)); MM_N=2048; TILES="32 64 128"
if [ "${QUICK:-0}" = 1 ]; then
  REPEAT=1; MINS=0.3; KS="1 4 16 64 256"; DRAM_N=$((16*1024*1024))
  [ $(( L3 * 1024 * 4 / 8 )) -gt $DRAM_N ] && DRAM_N=$(( L3 * 1024 * 4 / 8 ))
  TRIAD_N=$((16*1024*1024)); MM_N=1024; TILES="64"
fi

echo "exp,level,n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum" > "$OUT"
: > "$LOGF"
cool() {  # cool $start: idle COOLDOWN x (elapsed since start), so PL1 is never reached
  local el; el=$(python3 -c "import time;print(max(0.0,(time.time()-$1)*$COOLDOWN))")
  python3 -c "import time;time.sleep($el)"; }
record() {  # exp level K threads line errfile
  echo "$1,$2,$5" >> "$OUT"
  echo "  $1 $2 K=$3 thr=$4 -> $5"
  echo "$1,$2,K=$3,thr=$4 $(grep '^info:' "$6" | tr '\n' ' ')" >> "$LOGF"
  grep -v '^info:' "$6" >&2 || true; }
ERR=$(mktemp); trap 'rm -f "$ERR"' EXIT
run() {  # exp level n K threads
  for r in $(seq $REPEAT); do
    local s; s=$(python3 -c "import time;print(time.time())")
    line=$(OMP_NUM_THREADS=$5 ./bench $3 $4 $MINS 2>"$ERR")
    record $1 $2 $4 $5 "$line" "$ERR"
    cool $s
  done; }

# Idle power (for reference / sanity-check of pi0)
[ "${QUICK:-0}" = 1 ] || { echo "settling 20 s before idle measurement..."; sleep 20; }
python3 - <<'EOF' > "$OUTDIR/idle_power$SUF.txt" || true
import glob,time
fs=[f for f in glob.glob('/sys/class/powercap/intel-rapl:*/energy_uj') if f.count(':')==1
    and open(f.replace('energy_uj','name')).read().startswith('package')]
try:
    a=[int(open(f).read()) for f in fs]; time.sleep(5); b=[int(open(f).read()) for f in fs]
    print("idle_pkg_W=%.2f"%(sum(y-x for x,y in zip(a,b))/5e6))
except Exception as e: print("idle_pkg_W=nan")
EOF
cat "$OUTDIR/idle_power$SUF.txt"

if want intensity; then
echo "== Exp 1: intensity sweep (DRAM, all physical cores) =="
for K in $KS; do run intensity DRAM $DRAM_N $K $PHYS; done
fi

if want reuse; then
echo "== Exp 2: data reuse (working set in L1 / L2 / L3 / DRAM) =="
# working sets from the TOTAL capacity of each level (all instances; correct for hybrid
# CPUs whose cores have different cache sizes): half of L1d, half of L2, and for L3 a set
# larger than all L2s combined (else it would be served from L2) but well inside L3
N_L1=$(( L1 * 1024 / 2 / 8 ))
N_L2=$(( L2 * 1024 / 2 / 8 ))
N_L3=$(python3 -c "print(int(max($L3/2, min(0.8*$L3, 1.3*$L2))*1024/8))")
echo "  working sets: L1=$((N_L1*8/1024))K L2=$((N_L2*8/1024))K L3=$((N_L3*8/1024))K DRAM=$((DRAM_N*8/1048576))M"
for K in 1 2 4 8 16 64; do
  run reuse L1 $N_L1 $K $PHYS
  run reuse L2 $N_L2 $K $PHYS
  [ "$L3" -gt 0 ] && run reuse L3 $N_L3 $K $PHYS
  run reuse DRAM $DRAM_N $K $PHYS
done
fi

if want threads; then
echo "== Exp 3: thread scaling (low / medium / high intensity) =="
# OMP_PLACES=cores fills cores in id order (on hybrid Intel: P-cores first, then E-cores);
# counts above the physical core count use SMT siblings (OMP_PLACES=threads)
THR=$(python3 -c "
p=$PHYS; l=$LOG; s=sorted({1,2,4,6,8,12,16,24,32,48,64}&set(range(1,p+1))|{p}|({l} if l>p else set())); print(*s)")
for T in $THR; do
  [ "$T" -gt "$PHYS" ] && export OMP_PLACES=threads || export OMP_PLACES=cores
  for K in 1 16 256; do run threads DRAM $DRAM_N $K $T; done
done
export OMP_PLACES=cores
fi

if want real; then
echo "== Exp 4: real kernels (all physical cores) =="
# Q per rep from the memory-controller counters, by differencing a 1-rep and an R-rep run
# (cancels setup and warm-up), minus the background DRAM traffic measured while idle
QF="$OUTDIR/q_measured$SUF.csv"
echo "kernel,n,tile,threads,Q_analytic_per_rep,Q_measured_per_rep,method" > "$QF"
EV=$(ls -d /sys/bus/event_source/devices/uncore_imc_free_running_* 2>/dev/null | xargs -rn1 basename \
     | sed 's#.*#&/data_read/,&/data_write/#' | paste -sd, || true)
PS=$(mktemp)
mib() { awk -F, '$2=="MiB"{s+=$1} END{printf "%.3f", s}' "$1"; }
HAVE_PERF=0
if [ "${MEASURE_Q:-1}" = 1 ] && [ -n "$EV" ] && perf stat -a -x, -o "$PS" -e "$EV" sleep 3 2>/dev/null; then
  HAVE_PERF=1; IDLE_MIBS=$(python3 -c "print($(mib "$PS")/3)")
  echo "  perf IMC counters OK; idle DRAM traffic = $IDLE_MIBS MiB/s"
else
  echo "  perf IMC counters unavailable: using analytic Q"
fi
measure_q() {  # kernel n tile -> prints measured bytes per rep (or nothing)
  [ $HAVE_PERF = 1 ] || return 0
  local o1 o2 m1 m2 t1 t2 r2
  o1=$(REPS=1 OMP_NUM_THREADS=$PHYS perf stat -a -x, -o "$PS" -e "$EV" -- ./kernels $1 $2 $3 1 2>/dev/null) || return 0
  m1=$(mib "$PS"); t1=$(echo "$o1" | cut -d, -f8)
  r2=$(python3 -c "import math;print(1+max(2,math.ceil(2.0/$t1)))")
  o2=$(REPS=$r2 OMP_NUM_THREADS=$PHYS perf stat -a -x, -o "$PS" -e "$EV" -- ./kernels $1 $2 $3 1 2>/dev/null) || return 0
  m2=$(mib "$PS"); t2=$(echo "$o2" | cut -d, -f8)
  python3 -c "q=(($m2-$m1)-$IDLE_MIBS*($t2-$t1))*1048576/($r2-1); print('%.6e'%q if q>0 else '')"; }
runk() {  # kernel n tile
  local qa qm s
  s=$(python3 -c "import time;print(time.time())")
  qa=$(REPS=1 OMP_NUM_THREADS=$PHYS ./kernels $1 $2 $3 1 2>/dev/null | python3 -c "import sys;f=sys.stdin.read().split(',');print('%.6e'%(float(f[6])/float(f[4])))")
  qm=$(measure_q $1 $2 $3)
  local method=analytic; [ -n "$qm" ] && method=perf_imc_free_running
  echo "$1,$2,$3,$PHYS,$qa,$qm,$method" >> "$QF"
  echo "  $1 n=$2 tile=$3: Q/rep analytic=$qa measured=${qm:-n/a}"
  cool $s
  for r in $(seq $REPEAT); do
    s=$(python3 -c "import time;print(time.time())")
    line=$(Q_OVERRIDE=${qm:-0} OMP_NUM_THREADS=$PHYS ./kernels $1 $2 $3 $MINS 2>"$ERR")
    record real $1 "${3:-0}" $PHYS "$line" "$ERR"
    cool $s
  done; }
runk triad $TRIAD_N 0
runk matmul_naive $MM_N 0
for b in $TILES; do runk matmul_tiled $MM_N $b; done
rm -f "$PS"
fi

echo "Done -> $OUT. Now run: python3 analyze.py"
