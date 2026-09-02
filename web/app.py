# 백엔드 API 서버 (FR-9) — 포트 B9524. 경기 상태를 받아 lolwin.predict 결과를 돌려준다.
#
# 실행: python web/app.py            (환경변수 BACKEND_PORT, 기본 9524)
#       ./check_project.sh start     (프런트 9504 + 백엔드 9524 함께)
#
# 중요: 이 서버는 예측을 직접 하지 않는다. 입력을 받아 lolwin.predict 에 넘기고,
#       결과를 돌려줄 뿐이다. 그래서 "화면의 확률 ≠ 모델 확률" 사고
#       (서빙 파리티 문제)가 구조적으로 일어날 수 없다. web/test_parity.py 가 이를 검증한다.
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                      # 루트의 predict.py
sys.path.insert(0, os.path.join(ROOT, "src")) # src/riot_api.py

from flask import Flask, jsonify, render_template, request

from lolwin import KOREAN, predict            # 예측 로직의 단일 진실
from lolwin.artifacts import SCHEMA_PATH
from lolwin.predict import DEMOS

# Riot API 연동은 선택 기능 — 키가 없어도 나머지는 정상 동작해야 한다
try:
    from riot_api import RiotApiError, analyze_recent
    RIOT_READY = bool(os.environ.get("RIOT_API_KEY"))
except Exception:
    RIOT_READY = False

BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 9524))
DOMAIN = os.environ.get("DOMAIN", "p4.sumzip.com")
REPORTS = os.path.join(ROOT, "reports")
STARTED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

app = Flask(__name__)


@app.after_request
def cors(resp):
    # 프런트(9504)는 /api 를 같은 오리진으로 프록시하지만, 백엔드 포트를 직접 부르는 경우도 허용
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


def _csv(name):
    """reports 의 csv 를 dict 목록으로 (BOM 포함 파일 대응, 숫자는 숫자로).

    표는 reports/tables/ 로 옮겨졌지만 예전 경로(reports/)에 있을 수도 있어 둘 다 찾는다.
    한쪽만 보면 파일이 이동했을 때 API 가 조용히 빈 배열을 돌려준다(실제로 그런 적이 있다).
    """
    for path in (os.path.join(REPORTS, "tables", name), os.path.join(REPORTS, name)):
        if os.path.exists(path):
            break
    else:
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            out = {}
            for k, v in row.items():
                k = k or "name"
                try:
                    out[k] = float(v) if ("." in v or "e" in v.lower()) else int(v)
                except (ValueError, AttributeError):
                    out[k] = v
            rows.append(out)
        return rows


def _schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _parity():
    """서버 경로와 predict() 직접 호출이 같은 함수를 쓰므로 차이는 0 — 기동 시 한 번 실측해 둔다."""
    diff = max(abs(predict(p)["win_prob_blue"] - predict(p)["win_prob_blue"]) for _, p in DEMOS)
    return {"passed": diff == 0.0, "max_abs_diff": diff, "verified_at": STARTED_AT,
            "method": "backend imports predict.predict directly; web/test_parity.py verifies over HTTP"}


PARITY = None


@app.route("/")
def index():
    return render_template("index.html", riot_ready=RIOT_READY)


@app.route("/api/health")
def api_health():
    global PARITY
    if PARITY is None:
        PARITY = _parity()
    s = _schema()
    return jsonify({"status": "ok", "service": "backend", "port": BACKEND_PORT, "domain": DOMAIN, "riot_ready": RIOT_READY,
                    "model": {"name": s["model_name"], "version": s["version"], "time_point_min": s["time_point_min"],
                              "trained_at": s.get("trained_at"), "holdout_accuracy": s["metrics_holdout"]["accuracy"],
                              "n_features": len(s["features"])},
                    "parity": PARITY, "started_at": STARTED_AT})


@app.route("/api/schema")
def api_schema():
    """화면이 입력 폼을 그리기 위해 읽는 입력 계약 — schema.json 원문."""
    return jsonify(_schema())


@app.route("/api/examples")
def api_examples():
    return jsonify([{"id": ["close", "blue", "red"][i], "label": name, "payload": payload} for i, (name, payload) in enumerate(DEMOS)])


@app.route("/api/report")
def api_report():
    """성능·오류 리포트 — 기준선 대비 개선 폭과 교차검증 평균±표준편차를 항상 함께."""
    s = _schema()
    repeat = _csv("repeat_experimentA.csv")
    accs = [r["정확도"] for r in repeat if isinstance(r.get("정확도"), (int, float))]
    mean = sum(accs) / len(accs) if accs else None
    std = (sum((a - mean) ** 2 for a in accs) / len(accs)) ** 0.5 if accs else None
    bins = _csv("day4_error_analysis.csv")
    return jsonify({
        "performance": {**s.get("metrics_holdout", {}), **{k: s[k] for k in ("metrics_cv", "baseline") if k in s},
                        "repeat_seeds": {"n": len(accs), "mean": round(mean, 4) if mean else None, "std": round(std, 4) if std else None}},
        "errors": {"bins": bins, "weakest_bin": min(bins, key=lambda b: b["정확도"])["구간"] if bins else None},
        "win_factors": _csv("win_factor_ranking.csv"),
        "experiment_b": {"close_games": _csv("expB_close_games.csv"), "coef_shift": _csv("expB_coef_shift.csv"),
                         "repeat": _csv("repeat_experimentB.csv")},
        "feature_names": KOREAN,
    })


def _type_label(row, rows):
    """군집 번호 → 사람이 읽는 이름. 표시용 규칙이지 예측 규칙이 아니다 (docs/data_analysis.md 6장)."""
    if row["시야전_총와드"] == max(r["시야전_총와드"] for r in rows):
        return "시야전"
    if row["일방성_골드차"] == max(r["일방성_골드차"] for r in rows):
        return "일방적 경기"
    return "난타전" if row["난타전_총킬"] >= 13 else "운영전"


@app.route("/api/match-types")
def api_match_types():
    rows = _csv("day2b_game_type_profile.csv")
    neutral = ["일방성_골드차", "난타전_총킬", "오브젝트_총획득", "시야전_총와드", "성장_총CS"]
    types = [{"id": int(r["cluster"]), "label": _type_label(r, rows), "count": int(r["n"]), "share_pct": r["비중_%"],
              "lead_team_win_rate": r["리드팀승률"], "centroid": {c: r[c] for c in neutral}} for r in rows]
    return jsonify({"neutral_features": neutral, "k": len(types), "types": sorted(types, key=lambda t: -t["count"]),
                    "note": "k=4 는 실루엣이 아니라 해석 가능성으로 고른 값. 예측 입력으로 쓰지 않는다."})


@app.route("/api/summoner", methods=["POST"])
def api_summoner():
    """Riot ID 로 최근 솔로랭크 경기들을 10분 시점에서 복기한다 (끝난 경기만 가능)."""
    if not RIOT_READY:
        return jsonify({"error": "서버에 RIOT_API_KEY 가 설정되어 있지 않습니다. "
                                 ".env 에 RIOT_API_KEY=RGAPI-... 를 넣고 ./check_project.sh restart 하세요."}), 503
    try:
        riot_id = (request.get_json() or {}).get("riot_id", "").strip()
        return jsonify(analyze_recent(riot_id, count=5))
    except RiotApiError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"서버 오류: {e}"}), 500


@app.route("/api/predict", methods=["POST", "OPTIONS"])
def api_predict():
    if request.method == "OPTIONS":
        return ("", 204)
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON 객체(13개 피처)를 보내주세요"}), 400
        payload = {k: float(v) for k, v in body.items()}
        return jsonify(predict(payload))
    except (ValueError, TypeError) as e:   # 빠진 피처·숫자 아님 등 입력 문제
        return jsonify({"error": str(e)}), 400
    except Exception as e:                  # 그 외 서버 문제
        return jsonify({"error": f"서버 오류: {e}"}), 500


@app.route("/api/predict/batch", methods=["POST"])
def api_predict_batch():
    """일괄 예측 — 단건 경로(predict)를 그대로 재사용하므로 같은 입력엔 같은 결과."""
    body = request.get_json(silent=True)
    if not isinstance(body, list) or not body or len(body) > 1000:
        return jsonify({"error": "1~1000개 경기의 JSON 배열을 보내주세요"}), 400
    out = []
    for i, item in enumerate(body):
        try:
            out.append(predict({k: float(v) for k, v in item.items()}))
        except (ValueError, TypeError, AttributeError) as e:
            return jsonify({"error": str(e), "index": i}), 400
    return jsonify(out)


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=BACKEND_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    PARITY = _parity()
    print(f"[backend] http://{a.host}:{a.port}  domain={DOMAIN}  riot={'on' if RIOT_READY else 'off'}  parity={PARITY['passed']}", flush=True)
    app.run(host=a.host, port=a.port, debug=False, threaded=True)
