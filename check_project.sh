#!/usr/bin/env bash
# LoL 승패 예측·설명 서비스 — 시작/중지/재시작/상태/로그/테스트
#
#   ./check_project.sh start | stop | restart | status | logs | verify | test | health | deploy
#   verify = 서버 없이 도는 검사(회귀·계약·재현성·문서) — 커밋 전에 이것부터
#   deploy = git pull --ff-only → restart → test  (팀원이 main 에 push 한 뒤 팀 서버에 반영할 때)
#
# 포트·도메인 (DDBM 팀 배정): 프런트 F9504 · 백엔드 B9524 · p4.sumzip.com → 프런트
#   환경변수로 바꿀 수 있다: FRONTEND_PORT BACKEND_PORT DOMAIN
# 파이썬: venv311 (Python 3.11, requirements.txt 고정 버전) — 없으면 venv → python3
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1
FRONTEND_PORT="${FRONTEND_PORT:-9504}"
BACKEND_PORT="${BACKEND_PORT:-9524}"
DOMAIN="${DOMAIN:-p4.sumzip.com}"
export FRONTEND_PORT BACKEND_PORT DOMAIN
RUN="$ROOT/run"; LOG="$ROOT/logs"; mkdir -p "$RUN" "$LOG"

# .env 가 있으면 읽는다 (DB_PASSWORD · RIOT_API_KEY 등). 값은 출력하지 않는다.
if [ -f "$ROOT/.env" ]; then set -a; . "$ROOT/.env"; set +a; fi

# 파이썬 찾기 — "있는지" 가 아니라 "실제로 도는지" 로 고른다.
# 윈도우에는 python3 라는 이름의 마이크로소프트 스토어 안내 스텁이 있어서,
# -x 만 보면 그걸 골라 놓고 모든 명령이 조용히 실패한다(실제로 겪었다).
PY=""
for cand in "$ROOT/venv311/bin/python" "$ROOT/venv311/Scripts/python.exe" \
            "$ROOT/venv/bin/python" "$ROOT/venv/Scripts/python.exe" \
            python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
[ -n "$PY" ] || { echo "쓸 수 있는 python 을 못 찾았습니다 (python3 / python 확인)"; exit 1; }

c_ok()  { printf "\033[32m%s\033[0m\n" "$*"; }
c_bad() { printf "\033[31m%s\033[0m\n" "$*"; }

pid_of() { [ -f "$RUN/$1.pid" ] && cat "$RUN/$1.pid" 2>/dev/null; }
alive()  { local p; p=$(pid_of "$1"); [ -n "${p:-}" ] && kill -0 "$p" 2>/dev/null; }
port_pids() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null; }
http_code() { local c; c=$(curl -s -m "${2:-5}" -o /dev/null -w "%{http_code}" "$1" 2>/dev/null); echo "${c:-000}"; }

wait_up() {  # wait_up <url> <seconds>
  local i=0; while [ $i -lt "$2" ]; do [ "$(http_code "$1" 3)" = "200" ] && return 0; sleep 1; i=$((i+1)); done; return 1
}

start_one() {  # start_one <name> <script> <port> <health-url>
  local name=$1 script=$2 port=$3 url=$4
  if alive "$name"; then echo "$name: 이미 실행 중 (pid $(pid_of "$name"))"; return 0; fi
  if [ -n "$(port_pids "$port")" ]; then c_bad "$name: 포트 $port 를 다른 프로세스가 쓰고 있다 (pid $(port_pids "$port" | tr '\n' ' '))"; return 1; fi
  nohup "$PY" "$script" --port "$port" >> "$LOG/$name.log" 2>&1 &
  echo $! > "$RUN/$name.pid"
  if wait_up "$url" 25; then c_ok "$name: 시작됨 → http://0.0.0.0:$port (pid $(pid_of "$name"))"; else
    c_bad "$name: 기동 실패 — logs/$name.log 마지막 줄:"; tail -n 15 "$LOG/$name.log"; return 1; fi
}

stop_one() {  # stop_one <name> <port>
  local name=$1 port=$2 p
  p=$(pid_of "$name")
  if [ -n "${p:-}" ] && kill -0 "$p" 2>/dev/null; then
    kill "$p" 2>/dev/null; for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$p" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$p" 2>/dev/null && kill -9 "$p" 2>/dev/null
    echo "$name: 중지됨 (pid $p)"
  else echo "$name: 실행 중이 아님"; fi
  rm -f "$RUN/$name.pid"
  for q in $(port_pids "$port"); do kill "$q" 2>/dev/null && echo "$name: 포트 $port 잔여 프로세스 정리 (pid $q)"; done
}

cmd_start() {
  echo "▶ 시작  (python: $PY · 프런트 $FRONTEND_PORT · 백엔드 $BACKEND_PORT · 도메인 $DOMAIN)"
  [ -f "$ROOT/artifacts/model.joblib" ] || { c_bad "artifacts/model.joblib 이 없다 — 먼저 학습 산출물을 받아오거나 python src/finalize_model.py"; return 1; }
  "$PY" -c "import flask, sklearn, joblib" 2>/dev/null || { c_bad "$PY 에 flask/sklearn 이 없다 — python3.11 -m venv venv311 && venv311/bin/pip install -r requirements.txt"; return 1; }
  start_one backend  web/app.py      "$BACKEND_PORT"  "http://127.0.0.1:$BACKEND_PORT/api/health" || return 1
  start_one frontend web/frontend.py "$FRONTEND_PORT" "http://127.0.0.1:$FRONTEND_PORT/healthz"   || return 1
  echo "화면: http://127.0.0.1:$FRONTEND_PORT  ·  공개: https://$DOMAIN"
}
cmd_stop()    { echo "▶ 중지"; stop_one frontend "$FRONTEND_PORT"; stop_one backend "$BACKEND_PORT"; }
cmd_restart() { cmd_stop; sleep 1; cmd_start; }

cmd_status() {
  local rc=0
  echo "▶ 상태  (프런트 $FRONTEND_PORT · 백엔드 $BACKEND_PORT · 도메인 $DOMAIN)"
  for spec in "backend:$BACKEND_PORT:/api/health" "frontend:$FRONTEND_PORT:/healthz"; do
    IFS=: read -r name port path <<< "$spec"
    local p code; p=$(pid_of "$name"); code=$(http_code "http://127.0.0.1:$port$path")
    if alive "$name" && [ "$code" = "200" ]; then c_ok "  $name   실행 중  pid ${p}  포트 $port  health $code"
    else c_bad "  $name   중지/이상  pid ${p:-없음}  포트 $port  health $code  (listen: $(port_pids "$port" | tr '\n' ' '))"; rc=1; fi
  done
  local pub; pub=$(http_code "https://$DOMAIN/" 8)
  if [ "$pub" = "200" ]; then c_ok "  공개 도메인  https://$DOMAIN  → $pub"; else echo "  공개 도메인  https://$DOMAIN  → $pub  (200 이 아니면 수업 서버 프록시 설정을 확인)"; fi
  return $rc
}
cmd_logs()   { echo "▶ logs/backend.log"; tail -n "${1:-40}" "$LOG/backend.log" 2>/dev/null; echo; echo "▶ logs/frontend.log"; tail -n "${1:-40}" "$LOG/frontend.log" 2>/dev/null; }
cmd_health() { [ "$(http_code "http://127.0.0.1:$BACKEND_PORT/api/health")" = "200" ] && [ "$(http_code "http://127.0.0.1:$FRONTEND_PORT/healthz")" = "200" ] && { c_ok "healthy"; return 0; } || { c_bad "unhealthy"; return 1; }; }
cmd_deploy() {
  echo "▶ 배포: 최신 main 가져오기 → 재시작 → 테스트"
  git -C "$ROOT" pull --ff-only || { c_bad "git pull 실패 — 로컬 변경이 있으면 먼저 커밋/스태시"; return 1; }
  cmd_restart && cmd_test
}
# verify = 서버 없이 도는 검사 (라이브러리·문서). 커밋 전에 이것부터.
cmd_verify() {
  local fail=0
  echo "▶ 예측 회귀 (골든 50건)";      "$PY" tests/test_regression.py          || fail=1; echo
  echo "▶ 서빙 계약";                  "$PY" tests/test_contract.py            || fail=1; echo
  echo "▶ 학습 재현성";                "$PY" tests/test_training_reproducible.py || fail=1; echo
  echo "▶ 문서·수치 정합성";           "$PY" src/factcheck.py                  || fail=1
  [ "$fail" = 0 ] || { c_bad "verify 실패 — 위 항목을 먼저 고칠 것"; return 1; }
}

# test = verify + 서버가 떠 있어야 도는 검사
cmd_test() {
  cmd_verify || return 1
  echo; echo "▶ 서빙 파리티"; "$PY" web/test_parity.py || return 1
  echo;    echo "▶ API 스모크"; "$PY" web/test_api.py
}

case "${1:-}" in
  start) cmd_start ;;  stop) cmd_stop ;;  restart) cmd_restart ;;  status) cmd_status ;;
  logs) cmd_logs "${2:-40}" ;;  health) cmd_health ;;  test) cmd_test ;;
  verify) cmd_verify ;;  deploy) cmd_deploy ;;
  *) echo "사용법: $0 {start|stop|restart|status|logs [n]|health|test|deploy}"; exit 2 ;;
esac
