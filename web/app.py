# 웹 데모 (FR-9) — 경기 상태를 입력하면 승률과 이유를 보여주는 화면
#
# 실행: 프로젝트 폴더에서  python web/app.py
#       → 브라우저에서 http://localhost:5000 열기
#
# 중요: 이 서버는 예측을 직접 하지 않는다. 입력을 받아 predict.py 에 넘기고,
#       결과를 화면에 보여줄 뿐이다. 그래서 "화면의 확률 ≠ predict.py 확률" 사고
#       (서빙 파리티 문제)가 구조적으로 일어날 수 없다.
import os
import sys

# 프로젝트 루트를 import 경로에 추가 → 루트의 predict.py 를 가져올 수 있게
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template, request

from predict import predict  # 예측 로직의 단일 진실

# Riot API 연동은 선택 기능 — 키가 없어도 나머지 화면은 정상 동작해야 한다
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
try:
    from riot_api import RiotApiError, analyze_recent
    RIOT_READY = bool(os.environ.get("RIOT_API_KEY"))
except Exception:
    RIOT_READY = False

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", riot_ready=RIOT_READY)


@app.route("/api/summoner", methods=["POST"])
def api_summoner():
    """Riot ID 로 최근 솔로랭크 경기들을 10분 시점에서 복기한다 (끝난 경기만 가능)."""
    if not RIOT_READY:
        return jsonify({"error": "서버에 RIOT_API_KEY 가 설정되어 있지 않습니다. "
                                 "터미널에서 $env:RIOT_API_KEY='RGAPI-...' 설정 후 서버를 다시 켜세요."}), 503
    try:
        riot_id = (request.get_json() or {}).get("riot_id", "").strip()
        return jsonify(analyze_recent(riot_id, count=5))
    except RiotApiError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"서버 오류: {e}"}), 500


@app.route("/api/predict", methods=["POST"])
def api_predict():
    try:
        payload = {k: float(v) for k, v in request.get_json().items()}
        return jsonify(predict(payload))
    except ValueError as e:          # 빠진 피처 등 입력 문제
        return jsonify({"error": str(e)}), 400
    except Exception as e:           # 그 외 서버 문제
        return jsonify({"error": f"서버 오류: {e}"}), 500


if __name__ == "__main__":
    app.run(port=5000)
