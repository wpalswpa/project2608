#!/usr/bin/env bash
# 수집기 무인 실행 — 사람이 붙어 있을 필요가 없다.
#
#   ./scripts/run_collectors.sh          한 번 돌린다 (챔피언 → 랭킹 순서)
#   ./scripts/run_collectors.sh loop     끝나면 다시, 계속 (Ctrl+C 로 중단)
#
# 두 수집기 모두 이어받기라 중간에 끊겨도 다음 실행이 이어간다.
# 예산 양보(RESERVE 70)가 걸려 있어 라이브 사용자와 공존한다 —
# 예산 100 중 30만 쓰고 나머지는 사용자 몫으로 남긴다.
cd "$(dirname "$0")/.." || exit 1
# python3 이 Windows 스토어 스텁일 수 있다 — 실제로 코드가 도는 쪽을 고른다
PY=python3; "$PY" -c "pass" 2>/dev/null || PY=python
LOG=logs; mkdir -p "$LOG"

run_once() {
  echo "[$(date '+%H:%M:%S')] 챔피언 표본 수집 (40분)"
  "$PY" src/collect_champion_stats.py --minutes 40 --players 400 --per-player 15 \
    >> "$LOG/collect_champion.log" 2>&1
  echo "[$(date '+%H:%M:%S')] 랭킹 이름 수집"
  "$PY" src/collect_ranking.py --limit 1000 >> "$LOG/collect_ranking.log" 2>&1
  echo "[$(date '+%H:%M:%S')] 한 바퀴 완료"
}

if [ "$1" = "loop" ]; then
  while true; do run_once; echo "  5분 쉬고 다시 돕니다"; sleep 300; done
else
  run_once
fi
