# 프런트엔드 서버 — 포트 F9504 (도메인 p4.sumzip.com 이 여기로 온다).
#
# 하는 일 두 가지뿐:
#   1) 화면(web/templates/index.html)을 내려준다
#   2) /api/* 요청을 백엔드(127.0.0.1:9524)로 그대로 중계한다
# 그래서 화면 JS 는 상대경로 /api/... 만 부르면 되고, 도메인·포트가 바뀌어도 화면 코드는 안 바뀐다.
# 예측 로직은 여기에 한 줄도 없다 (서빙 파리티).
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from flask import Flask, Response, render_template, request, send_from_directory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", 9504))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 9524))
BACKEND = os.environ.get("BACKEND_URL", f"http://127.0.0.1:{BACKEND_PORT}")
DOMAIN = os.environ.get("DOMAIN", "p4.sumzip.com")

app = Flask(__name__, template_folder=os.path.join(ROOT, "web", "templates"))


def _backend(path, method="GET", body=None, timeout=30):
    req = urllib.request.Request(BACKEND + path, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", "application/json"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "application/json"), e.read()
    except Exception as e:
        return 502, "application/json", json.dumps({"error": f"백엔드({BACKEND})에 연결할 수 없습니다: {e}"}, ensure_ascii=False).encode()


@app.route("/")
def index():
    status, _, raw = _backend("/api/health", timeout=5)
    riot_ready = False
    if status == 200:
        try:
            riot_ready = bool(json.loads(raw).get("riot_ready"))
        except Exception:
            pass
    return render_template("index.html", riot_ready=riot_ready, domain=DOMAIN, backend_ok=(status == 200))


@app.route("/figures/<path:name>")
def figures(name):
    """reports/ 의 그림을 그대로 내려준다.

    web/static/ 에 사본을 두면 그림을 다시 만들 때마다 손으로 복사해야 하고,
    깜빡하면 화면만 옛 그림이 남는다(실제로 그런 적이 있다).
    사본을 없애고 원본을 직접 서빙하므로, git pull 만 하면 화면도 같이 최신이 된다.
    send_from_directory 가 경로 탈출(../)을 막아 준다.
    """
    for sub in ("", "figures"):
        d = os.path.join(ROOT, "reports", sub)
        if os.path.isfile(os.path.join(d, name)):
            return send_from_directory(d, name, max_age=60)
    return ({"error": f"reports 에 {name} 이 없습니다"}, 404)


@app.route("/healthz")
def healthz():
    status, _, _ = _backend("/api/health", timeout=5)
    return {"status": "ok", "service": "frontend", "port": FRONTEND_PORT, "domain": DOMAIN, "backend": BACKEND, "backend_ok": status == 200}


@app.route("/api/<path:path>", methods=["GET", "POST", "OPTIONS"])
def proxy(path):
    if request.method == "OPTIONS":
        return ("", 204)
    body = request.get_data() if request.method == "POST" else None
    q = ("?" + request.query_string.decode()) if request.query_string else ""
    status, ctype, raw = _backend("/api/" + path + q, request.method, body)
    return Response(raw, status=status, content_type=ctype)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=FRONTEND_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    print(f"[frontend] http://{a.host}:{a.port}  domain={DOMAIN}  backend={BACKEND}", flush=True)
    app.run(host=a.host, port=a.port, debug=False, threaded=True)
