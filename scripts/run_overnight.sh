#!/usr/bin/env bash
# 밤새 돌리는 수집 — 랭킹 이름 → 챔피언 표본(대량) → 티어 연구 순서.
#
#   ./scripts/run_overnight.sh
#
# 셋 다 이어받기라 중간에 끊겨도 다음 실행이 이어간다.
# 예산 양보(RESERVE 70)가 걸려 있어 라이브 사용자와 공존한다.
cd "$(dirname "$0")/.." || exit 1
# python3 이 Windows 스토어 스텁일 수 있다 — 실제로 코드가 도는 쪽을 고른다
PY=python3; "$PY" -c "pass" 2>/dev/null || PY=python
mkdir -p logs

echo "[$(date '+%H:%M:%S')] 1/3 랭킹 이름"
"$PY" -u src/collect_ranking.py --limit 1000 >> logs/collect_ranking.log 2>&1

# 챔피언 표본이 조합당 평균 7판밖에 안 됐다. 조합이 275개라 판수를 크게 늘려야
# 조합당 표본이 는다 — 3시간이면 대략 8,000판 이상 쌓인다.
echo "[$(date '+%H:%M:%S')] 2/3 챔피언 표본 (180분)"
"$PY" -u src/collect_champion_stats.py --minutes 180 --players 900 --per-player 20 \
  >> logs/collect_champion.log 2>&1

echo "[$(date '+%H:%M:%S')] 3/3 티어 연구"
for T in IRON BRONZE SILVER GOLD PLATINUM EMERALD DIAMOND; do
  echo "  [$(date '+%H:%M:%S')] $T"
  "$PY" -u src/tier_generalization.py --collect --tier "$T" --games 150 \
    >> logs/tier_study.log 2>&1
done
"$PY" -u src/tier_generalization.py --report >> logs/tier_study.log 2>&1
echo "[$(date '+%H:%M:%S')] 전부 완료"
