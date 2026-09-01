# 프론트엔드 서버 (포트 9504) — 팀원·시연자가 접속하는 곳
#
# 실행: python web/frontend.py
# 접속: http://p4.sumzip.com:9504  (도메인이 이 포트로 매핑된다)
#
# 하는 일 두 가지
#   1. 화면(templates/index.html)을 보여준다
#   2. 화면이 보낸 /api/* 요청을 백엔드(9524)로 그대로 넘기고 답을 돌려준다
#
# 왜 넘기기만 하나 — 브라우저가 백엔드를 직접 부르면 주소가 두 개가 되어
# 도메인 매핑과 CORS 설정이 둘 다 필요해진다. 여기서 대신 불러주면 브라우저는 9504 하나만 알면 된다.
# 그리고 여기에는 예측 코드가 한 줄도 없다. 계산은 백엔드 뒤의 predict.py 만 한다.
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, Response, jsonify, render_template, request

from config import BACKEND_URL, BIND_HOST, DOMAIN, FRONTEND_PORT

app = Flask(__name__)


def _riot_ready():
    """백엔드에 물어봐서 라이엇 기능이 켜져 있는지 확인한다 (백엔드가 꺼져 있으면 False)."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=3) as r:
            return json.load(r).get("riot_api") == "사용 가능"
    except Exception:
        return False


@app.get("/")
def index():
    return render_template("index.html", riot_ready=_riot_ready())


@app.get("/health")
def health():
    """프론트와 백엔드가 둘 다 살아 있는지 한 번에 확인한다."""
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=5) as r:
            backend = json.load(r)
        return jsonify({"status": "ok", "service": "frontend", "port": FRONTEND_PORT,
                        "domain": DOMAIN, "backend": backend})
    except Exception as e:
        return jsonify({"status": "backend_down", "service": "frontend",
                        "port": FRONTEND_PORT, "detail": str(e)}), 503


@app.post("/api/<path:endpoint>")
def proxy(endpoint):
    """화면이 보낸 요청을 백엔드로 넘긴다. 내용은 건드리지 않는다."""
    url = f"{BACKEND_URL}/api/{endpoint}"
    body = request.get_data() or b"{}"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Response(r.read(), status=r.status, content_type="application/json")
    except urllib.error.HTTPError as e:
        # 백엔드가 돌려준 오류 메시지를 그대로 전달한다 (사용자가 원인을 알 수 있게)
        return Response(e.read(), status=e.code, content_type="application/json")
    except urllib.error.URLError:
        return jsonify({"error": "예측 서버(백엔드)에 연결할 수 없습니다. "
                                 "./check_project.sh status 로 상태를 확인하세요."}), 503
    except Exception as e:
        return jsonify({"error": f"요청 전달 실패: {e}"}), 500


if __name__ == "__main__":
    print(f"[프론트엔드] 화면 — http://{BIND_HOST}:{FRONTEND_PORT}  (도메인: {DOMAIN})")
    print(f"[프론트엔드] 예측 요청은 {BACKEND_URL} 로 전달합니다")
    app.run(host=BIND_HOST, port=FRONTEND_PORT, debug=False, threaded=True)
