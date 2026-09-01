# 백엔드 API 서버 (포트 9524)
#
# 실행: python web/backend.py
#
# 하는 일: 예측 요청을 받아 predict.py 에 넘기고 결과를 JSON 으로 돌려준다.
# 하지 않는 일: 예측 계산. 그건 predict.py 하나만 한다.
#   여기에 계산을 또 만들면 화면 확률과 모델 확률이 갈라져도 아무도 모른다.
#
# 이 서버는 바깥에 직접 노출하지 않는다. 프론트엔드(9504)만 호출한다.
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request

from config import BACKEND_PORT, BIND_HOST
from predict import predict  # 예측 로직의 단일 진실

# 라이엇 연동은 선택 기능 — 키가 없어도 나머지는 정상 동작해야 한다
try:
    from riot_api import RiotApiError, analyze_recent
    RIOT_AVAILABLE = True
except Exception:
    RIOT_AVAILABLE = False

    class RiotApiError(Exception):
        pass

app = Flask(__name__)


@app.get("/api/health")
def health():
    """서비스가 살아 있는지 확인하는 곳. check_project.sh 가 이걸 본다."""
    try:
        # 모델이 실제로 로드되고 예측이 되는지까지 확인한다 (그냥 살아만 있는 게 아니라)
        from predict import _load
        _, schema = _load()
        return jsonify({
            "status": "ok",
            "service": "backend",
            "port": BACKEND_PORT,
            "model": schema.get("model_name"),
            "features": len(schema.get("features", {})),
            "holdout_accuracy": schema.get("metrics_holdout", {}).get("accuracy"),
            "riot_api": "사용 가능" if (RIOT_AVAILABLE and os.environ.get("RIOT_API_KEY")) else "미설정",
        })
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@app.post("/api/predict")
def api_predict():
    """경기 상태 13개 → 승률·예측·요인·경고"""
    try:
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "입력이 비어 있습니다. 13개 지표를 JSON 으로 보내주세요."}), 400
        payload = {k: float(v) for k, v in body.items()}
        return jsonify(predict(payload))
    except ValueError as e:
        # 빠진 지표, 숫자가 아닌 값 등 — 사용자가 고칠 수 있는 문제
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"서버 오류: {e}"}), 500


@app.post("/api/summoner")
def api_summoner():
    """Riot ID 로 최근 솔로랭크 경기를 10분 시점에서 복기한다 (끝난 경기만 가능)."""
    if not (RIOT_AVAILABLE and os.environ.get("RIOT_API_KEY")):
        return jsonify({"error": "RIOT_API_KEY 가 설정되어 있지 않습니다. "
                                 "키를 환경변수로 넣고 서비스를 다시 시작하세요."}), 503
    try:
        riot_id = (request.get_json(silent=True) or {}).get("riot_id", "").strip()
        if not riot_id:
            return jsonify({"error": "Riot ID 를 입력해 주세요 (예: 홍길동#KR1)"}), 400
        return jsonify(analyze_recent(riot_id, count=5))
    except RiotApiError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"서버 오류: {e}"}), 500


if __name__ == "__main__":
    print(f"[백엔드] 예측 API — http://{BIND_HOST}:{BACKEND_PORT}")
    app.run(host=BIND_HOST, port=BACKEND_PORT, debug=False, threaded=True)
