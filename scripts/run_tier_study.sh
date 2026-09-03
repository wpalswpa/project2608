#!/usr/bin/env bash
# 티어별 일반화 검증 — 티어를 돌아가며 모으고 마지막에 채점한다.
# 이어받기라 중간에 끊겨도 다시 실행하면 이어간다.
cd "$(dirname "$0")/.." || exit 1
PY=$(command -v python3 || command -v python)
mkdir -p logs
N=${1:-150}                      # 티어당 목표 경기 수
for T in IRON BRONZE SILVER GOLD PLATINUM EMERALD DIAMOND; do
  echo "[$(date '+%H:%M:%S')] $T 수집 ($N판)"
  "$PY" src/tier_generalization.py --collect --tier "$T" --games "$N" \
    >> logs/tier_study.log 2>&1
done
"$PY" src/tier_generalization.py --report | tee -a logs/tier_study.log
