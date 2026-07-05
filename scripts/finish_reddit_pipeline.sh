#!/usr/bin/env bash
# Auto-resume the full coding pipeline across Groq TPM windows.
# Alternates gpt-oss-120b / llama-3.3-70b each iteration, sleeps 65s between
# attempts so the per-minute token bucket refreshes. Runs to completion:
#   1) theme classification (classify.py)   until 0 remaining
#   2) evidence-gated re-segmentation        until all evidence_gated
#   3) job-to-be-done coding                 until all jtbd v1
#   4) aggregate + export data.ts
set -u
cd "$(dirname "$0")/.."
source .venv/bin/activate

# 8B-instant first (high TPM/daily limits → won't stall), 70B as fallback.
MODELS=("llama-3.1-8b-instant" "llama-3.3-70b-versatile")
mi=0
SLEEP_BETWEEN=12   # 8B rarely rate-limits, so short waits

remaining_classify() {
  python3 -c "import sqlite3;c=sqlite3.connect('data/reviews.db');print(c.execute('SELECT COUNT(*) FROM reviews r LEFT JOIN coded_reviews c ON c.id=r.id WHERE r.relevant=1 AND c.id IS NULL').fetchone()[0])"
}
remaining_reseg() {
  python3 -c "import sqlite3;c=sqlite3.connect('data/reviews.db');print(c.execute(\"SELECT COUNT(*) FROM coded_reviews WHERE seg_method IS NULL OR seg_method!='evidence_gated'\").fetchone()[0])"
}
remaining_jtbd() {
  python3 -c "import sqlite3;c=sqlite3.connect('data/reviews.db');print(c.execute(\"SELECT COUNT(*) FROM coded_reviews WHERE jtbd_method IS NULL OR jtbd_method!='v1'\").fetchone()[0])"
}

run_until() {
  # $1 = check fn name, $2 = pipeline script + flag template using {M} for model
  local checkfn="$1"; shift
  local tries=0
  while [ "$($checkfn)" -gt 0 ] && [ "$tries" -lt 90 ]; do
    local model="${MODELS[$((mi % 2))]}"; mi=$((mi+1)); tries=$((tries+1))
    echo ">>> [$checkfn] remaining=$($checkfn)  model=$model  try=$tries"
    python "$@" --model "$model" 2>&1 | tail -2
    [ "$($checkfn)" -gt 0 ] && sleep "$SLEEP_BETWEEN"
  done
}

echo "===== STAGE 1: theme classification ====="
run_until remaining_classify pipeline/classify.py
echo "classify remaining: $(remaining_classify)"

echo "===== STAGE 2: evidence-gated re-segmentation ====="
run_until remaining_reseg pipeline/resegment.py
echo "reseg remaining: $(remaining_reseg)"

echo "===== STAGE 3: job-to-be-done coding ====="
run_until remaining_jtbd pipeline/classify_jtbd.py
echo "jtbd remaining: $(remaining_jtbd)"

echo "===== STAGE 4: aggregate + export ====="
python pipeline/aggregate.py 2>&1 | tail -3
python pipeline/export_data.py 2>&1 | tail -3

echo "===== STAGE 5: rebuild vector index (so Ask/RAG covers Reddit) ====="
python app/build_index.py 2>&1 | tail -3

echo "===== PIPELINE COMPLETE ====="
python3 -c "
import sqlite3
c=sqlite3.connect('data/reviews.db')
print('relevant by source:')
for s,n in c.execute('SELECT source,COUNT(*) AS n FROM reviews WHERE relevant=1 GROUP BY source ORDER BY n DESC'): print(f'  {s}: {n}')
print('coded:', c.execute('SELECT COUNT(*) FROM coded_reviews').fetchone()[0])
c.close()
"
