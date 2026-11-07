#!/usr/bin/env bash
# run.sh - runs all three experiments and writes results.csv
# Usage:  ./run.sh            (full run, roughly 15-25 min)
#         QUICK=1 ./run.sh    (fast smoke test, ~2 min)
set -euo pipefail
cd "$(dirname "$0")"

gcc -O3 -march=native -fopenmp -o bench bench.c

# ---------- machine info ----------
PHYS=$(lscpu -p=CORE,SOCKET | grep -v '^#' | sort -u | wc -l)   # physical cores
LOG=$(nproc)                                                    # logical CPUs (with SMT)
cache_kb() {  # per-instance size of cache level $1 (data/unified), in KB
  for d in /sys/devices/system/cpu/cpu0/cache/index*; do
    if [ "$(cat $d/level)" = "$1" ] && [ "$(cat $d/type)" != "Instruction" ]; then
      s=$(cat $d/size); case $s in *K) echo ${s%K};; *M) echo $(( ${s%M} * 1024 ));; esac; return
    fi
  done; echo 0; }
L1=$(cache_kb 1); L2=$(cache_kb 2); L3=$(cache_kb 3)
lscpu > machine_info.txt
echo "physical_cores=$PHYS logical=$LOG L1=${L1}K L2=${L2}K L3=${L3}K" | tee -a machine_info.txt

export OMP_PROC_BIND=close OMP_PLACES=cores
REPEAT=3; MINS=1.0
KS="1 2 4 8 16 32 64 128 256 512"
DRAM_N=$(( 64 * 1024 * 1024 ))          # 64M doubles = 512 MB (well beyond L3)
[ $(( L3 * 1024 * 4 / 8 )) -gt $DRAM_N ] && DRAM_N=$(( L3 * 1024 * 4 / 8 ))   # at least 4x L3
if [ "${QUICK:-0}" = 1 ]; then REPEAT=1; MINS=0.3; KS="1 4 16 64 256"; DRAM_N=$((16*1024*1024)); [ $(( L3 * 1024 * 4 / 8 )) -gt $DRAM_N ] && DRAM_N=$(( L3 * 1024 * 4 / 8 )); fi

OUT=results.csv
echo "exp,level,n,bytes,K,threads,reps,W,Q,time_s,E_pkg_J,E_dram_J,checksum" > $OUT
run() {  # exp level n K threads
  for r in $(seq $REPEAT); do
    line=$(OMP_NUM_THREADS=$5 ./bench $3 $4 $MINS)
    echo "$1,$2,$line" >> $OUT
    echo "  $1 $2 K=$4 thr=$5 -> $line"
  done; }

# Idle power (for reference / sanity-check of pi0)
python3 - <<'EOF' > idle_power.txt || true
import glob,time
fs=[f for f in glob.glob('/sys/class/powercap/intel-rapl:*/energy_uj') if f.count(':')==1]
try:
    a=[int(open(f).read()) for f in fs]; time.sleep(5); b=[int(open(f).read()) for f in fs]
    print("idle_pkg_W=%.2f"%(sum(y-x for x,y in zip(a,b))/5e6))
except Exception as e: print("idle_pkg_W=nan")
EOF
cat idle_power.txt

echo "== Exp 1: intensity sweep (DRAM, all physical cores) =="
for K in $KS; do run intensity DRAM $DRAM_N $K $PHYS; done

echo "== Exp 2: data reuse (working set in L1 / L2 / L3 / DRAM) =="
# working set = half the cache; L1/L2 are per core, so scale by thread count
N_L1=$(( L1 * 1024 / 2 / 8 * PHYS ))
N_L2=$(( L2 * 1024 / 2 / 8 * PHYS ))
N_L3=$(( L3 * 1024 / 2 / 8 ))
for K in 1 2 4 8 16 64; do
  run reuse L1 $N_L1 $K $PHYS
  run reuse L2 $N_L2 $K $PHYS
  [ "$L3" -gt 0 ] && run reuse L3 $N_L3 $K $PHYS
  run reuse DRAM $DRAM_N $K $PHYS
done

echo "== Exp 3: thread scaling (low / medium / high intensity) =="
THR=$(python3 -c "
p=$PHYS; l=$LOG; s=sorted({1,2,4,6,8,12,16,24,32,48,64}&set(range(1,p+1))|{p}|({l} if l>p else set())); print(*s)")
for T in $THR; do
  [ "$T" -gt "$PHYS" ] && export OMP_PLACES=threads || export OMP_PLACES=cores
  for K in 1 16 256; do run threads DRAM $DRAM_N $K $T; done
done

echo "Done -> $OUT. Now run: python3 analyze.py"
