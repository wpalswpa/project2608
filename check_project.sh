#!/usr/bin/env bash
# ============================================================================
# check_project.sh — 서비스 시작 / 중지 / 재시작 / 상태 확인
#
#   ./check_project.sh start      두 서버를 켠다
#   ./check_project.sh stop       두 서버를 끈다
#   ./check_project.sh restart    껐다가 켠다
#   ./check_project.sh status     지금 상태를 보여준다 (실제로 응답하는지까지 확인)
#   ./check_project.sh logs       최근 로그를 보여준다
#
# 구성
#   프론트엔드 9504  ← 도메인 p4.sumzip.com 이 여기로 연결된다. 팀원은 여기로 접속
#   백엔드     9524  ← 예측 담당. 프론트엔드만 부른다
# ============================================================================
set -uo pipefail

cd "$(dirname "$0")" || exit 1

FRONTEND_PORT="${FRONTEND_PORT:-9504}"
BACKEND_PORT="${BACKEND_PORT:-9524}"
DOMAIN="${SERVICE_DOMAIN:-p4.sumzip.com}"

RUN_DIR="run"
LOG_DIR="logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

# 파이썬 찾기 — 이름이 있는 것만으로는 부족하다.
# 윈도우에는 실행하면 스토어만 여는 가짜 python3 가 있어서, 실제로 돌아가는지 확인한다.
PY=""
for cand in "${PYTHON:-}" python3 python py; do
    [ -n "$cand" ] || continue
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
        PY="$cand"; break
    fi
done
if [ -z "$PY" ]; then
    printf '\033[31m파이썬을 찾을 수 없습니다.\033[0m 설치 후 다시 실행하거나 PYTHON=/경로/python 으로 지정하세요.\n'
    exit 1
fi

# ---------------------------------------------------------------- 도우미
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
gray()  { printf '\033[90m%s\033[0m\n' "$1"; }

pid_file() { echo "$RUN_DIR/$1.pid"; }
log_file() { echo "$LOG_DIR/$1.log"; }

# 저장해 둔 PID 가 실제로 살아 있는지 확인 (죽은 PID 파일은 지운다)
is_running() {
    local f; f=$(pid_file "$1")
    [ -f "$f" ] || return 1
    local pid; pid=$(cat "$f" 2>/dev/null)
    [ -n "$pid" ] || { rm -f "$f"; return 1; }
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    rm -f "$f"
    return 1
}

# 포트를 이미 다른 프로그램이 쓰고 있는지 확인
port_busy() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti tcp:"$port" >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -q ":$port "
    else
        netstat -an 2>/dev/null | grep -q "[:.]$port .*LISTEN"
    fi
}

# 서비스가 실제로 응답하는지 확인 (프로세스만 살아 있고 먹통인 경우를 걸러낸다)
responds() {
    local url=$1
    if command -v curl >/dev/null 2>&1; then
        curl -sf --max-time 5 "$url" >/dev/null 2>&1
    else
        "$PY" - "$url" <<'EOF' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=5)
EOF
    fi
}

# ---------------------------------------------------------------- 시작
start_one() {
    local name=$1 script=$2 port=$3
    if is_running "$name"; then
        gray "  $name — 이미 켜져 있습니다 (PID $(cat "$(pid_file "$name")"))"
        return 0
    fi
    if port_busy "$port"; then
        red "  $name — 포트 $port 를 다른 프로그램이 쓰고 있습니다"
        echo "     확인: lsof -i :$port   (또는 netstat -ano | findstr $port)"
        return 1
    fi
    nohup "$PY" "$script" >> "$(log_file "$name")" 2>&1 &
    echo $! > "$(pid_file "$name")"
    sleep 0.5
}

cmd_start() {
    echo "서비스를 시작합니다"
    start_one backend  web/backend.py  "$BACKEND_PORT"  || return 1
    start_one frontend web/frontend.py "$FRONTEND_PORT" || return 1

    # 뜰 때까지 기다린다 (모델 로딩에 몇 초 걸린다)
    printf "  준비 중"
    local ok=0
    for _ in $(seq 1 30); do
        if responds "http://127.0.0.1:$BACKEND_PORT/api/health" \
           && responds "http://127.0.0.1:$FRONTEND_PORT/health"; then
            ok=1; break
        fi
        printf "."
        sleep 1
    done
    echo
    if [ "$ok" = 1 ]; then
        green "  시작 완료"
        echo
        cmd_status
    else
        red "  시작했지만 응답이 없습니다. 로그를 확인하세요:"
        echo "     ./check_project.sh logs"
        return 1
    fi
}

# ---------------------------------------------------------------- 중지
stop_one() {
    local name=$1
    if ! is_running "$name"; then
        gray "  $name — 이미 꺼져 있습니다"
        return 0
    fi
    local pid; pid=$(cat "$(pid_file "$name")")
    kill "$pid" 2>/dev/null
    for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null   # 안 죽으면 강제 종료
        sleep 0.5
    fi
    rm -f "$(pid_file "$name")"
    green "  $name — 중지했습니다"
}

cmd_stop() {
    echo "서비스를 중지합니다"
    stop_one frontend
    stop_one backend
}

# ---------------------------------------------------------------- 상태
show_one() {
    local name=$1 port=$2 url=$3
    printf "  %-10s 포트 %-6s " "$name" "$port"
    if is_running "$name"; then
        if responds "$url"; then
            green "정상 (PID $(cat "$(pid_file "$name")"))"
        else
            red "응답 없음 — 켜져 있지만 먹통입니다. restart 를 해보세요"
        fi
    else
        gray "꺼져 있음"
    fi
}

cmd_status() {
    echo "서비스 상태"
    show_one backend  "$BACKEND_PORT"  "http://127.0.0.1:$BACKEND_PORT/api/health"
    show_one frontend "$FRONTEND_PORT" "http://127.0.0.1:$FRONTEND_PORT/health"
    echo
    if responds "http://127.0.0.1:$FRONTEND_PORT/health"; then
        echo "  접속 주소"
        echo "    팀원·시연  http://$DOMAIN:$FRONTEND_PORT"
        echo "    이 서버에서  http://127.0.0.1:$FRONTEND_PORT"
        # 모델이 제대로 물려 있는지도 같이 보여준다
        "$PY" - "$BACKEND_PORT" <<'EOF' 2>/dev/null
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/api/health", timeout=5) as r:
        d = json.load(r)
    print(f"\n  모델  {d.get('model')} · 입력 {d.get('features')}개 · 정확도 {d.get('holdout_accuracy')}")
    print(f"  라이엇 연동  {d.get('riot_api')}")
except Exception:
    pass
EOF
    fi
}

# ---------------------------------------------------------------- 로그
cmd_logs() {
    for name in backend frontend; do
        local f; f=$(log_file "$name")
        echo "=== $name ==="
        [ -f "$f" ] && tail -n "${LINES:-20}" "$f" || gray "  (로그 없음)"
        echo
    done
}

# ---------------------------------------------------------------- 진입점
case "${1:-status}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_stop; echo; cmd_start ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    *)
        echo "사용법: $0 {start|stop|restart|status|logs}"
        echo
        echo "  start    서비스를 켠다 (프론트 $FRONTEND_PORT · 백엔드 $BACKEND_PORT)"
        echo "  stop     서비스를 끈다"
        echo "  restart  껐다가 켠다"
        echo "  status   지금 상태 확인 (실제 응답까지 확인)"
        echo "  logs     최근 로그 20줄"
        exit 1
        ;;
esac
