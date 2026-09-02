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
from lolwin.features import gold_bin_bounds
from lolwin.artifacts import SCHEMA_PATH
from lolwin.predict import DEMOS

# Riot API 연동은 선택 기능 — 키가 없어도 나머지는 정상 동작해야 한다
try:
    from riot_api import RiotApiError, analyze_recent, key_works
    # 키가 '있는지' 가 아니라 '지금 통하는지' 를 본다. 개발용 키는 24시간마다 죽는데,
    # 죽은 키로 화면이 소환사 검색을 권하면 시연 중에 고장 난 것처럼 보인다.
    RIOT_READY = key_works()
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
    # 화면이 "이 경기는 어느 구간인가"를 판정하려면 경계값이 필요하다.
    # 화면에 숫자를 다시 적지 않도록 서버가 상한을 함께 내려준다 (경계 정본은 lolwin/features.py).
    bounds = dict(gold_bin_bounds())
    for b in bins:
        hi = bounds.get(b.get("구간"))
        b["max_gold"] = None if hi is None or hi == float("inf") else hi
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


# ── 실제 경기 복기 (/api/matches) ──────────────────────────────
# 왜 이 기능이 필요한가:
#   Riot API 키 없이도 "진짜 경기"를 보여줘야 서비스가 성립한다.
#   시험셋 1,976판은 학습에 한 번도 안 쓴 실제 경기이고 최종 승패를 안다.
#   그래서 "10분 시점 예측 vs 실제 결과" 를 그대로 복기할 수 있다.
#   모델이 맞힌 판뿐 아니라 **틀린 판도 숨기지 않고** 보여주는 것이 이 서비스의 태도다.
_MATCHES = None            # 서버 기동 후 첫 요청 때 한 번만 계산해 캐시


def _build_matches():
    """시험셋 전체를 미리 예측해 복기 카드 목록으로 만든다.

    1,976판을 매 요청마다 예측하면 느리므로 한 번만 계산한다.
    (13개 피처 * 1,976행이라 메모리 부담은 없다)
    """
    from lolwin.coach import verdict_of
    from lolwin.data import load
    from lolwin.features import DIFF13, KOREAN, gold_bin_bounds

    _, _, X_te, y_te, _ = load()
    bounds = gold_bin_bounds()
    out = []
    for idx in X_te.index:
        row = {f: float(X_te.at[idx, f]) for f in DIFF13}
        r = predict(row)
        gold = abs(row["GoldDiff"])
        band = next((lab for lab, hi in bounds if gold < hi), bounds[-1][0])
        actual = int(y_te.loc[idx])
        out.append({
            "id": int(idx),
            "gold_diff": int(row["GoldDiff"]),
            "kills_diff": int(row["KillsDiff"]),
            "dragons_diff": int(row["DragonsDiff"]),
            "exp_diff": int(row["ExpDiff"]),
            "band": band,
            "win_prob_blue": r["win_prob_blue"],
            "pred": r["pred"],
            "actual": actual,
            "correct": r["pred"] == actual,
            # 샘플 경기는 '블루 팀 관점'으로 판정한다 (소환사 경기는 그 사람 팀 관점)
            "verdict": verdict_of(r["win_prob_blue"], bool(actual)),
            # 근거 3개면 카드에 충분하다 (5개는 카드가 길어진다)
            "top_factors": [{"name": f["name"], "contribution": f["contribution"]}
                            for f in r["top_factors"][:3]],
            "features": row,
        })
    return out


@app.route("/api/coach", methods=["POST"])
def api_coach():
    """감독 — 이 경기 상태에서 무엇을 했다면 승률이 얼마나 올랐나.

    진단(어디서 졌나)에서 멈추지 않고 처방까지 준다.
    계산은 lolwin.coach 한 곳에서만 한다 — 화면은 문장만 만든다.
    """
    from lolwin.coach import advise, verdict_advice

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON 본문이 필요합니다."}), 400
    try:
        out = advise({k: v for k, v in data.items() if k != "verdict"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if data.get("verdict"):
        out["verdict_advice"] = verdict_advice(data["verdict"])
    return jsonify(out)


@app.route("/api/matches")
def api_matches():
    """실제 경기 복기 — 시험셋에서 조건에 맞는 경기를 돌려준다.

    질의 인자
      band     구간 이름으로 거르기 (예: "접전(<1k)")
      correct  "1" 맞힌 것만 · "0" 틀린 것만
      limit    최대 개수 (기본 12, 최대 60)
      offset   더 보기용 시작 위치
      seed     같은 seed 면 같은 순서 — "더 보기" 가 중복되지 않게
    """
    global _MATCHES
    if _MATCHES is None:
        _MATCHES = _build_matches()

    rows = _MATCHES

    # 경기 번호 직접 조회 — 검색창의 "#7758 찾기" 용. 있으면 그 한 판만 돌려준다.
    match_id = request.args.get("id")
    if match_id:
        try:
            want = int(match_id)
        except ValueError:
            return jsonify({"error": "경기 번호는 숫자입니다."}), 400
        hitrows = [m for m in rows if m["id"] == want]
        return jsonify({"total": len(hitrows), "accuracy": None, "offset": 0,
                        "returned": len(hitrows), "matches": hitrows,
                        "note": "경기 번호로 찾은 결과입니다."})

    band = request.args.get("band")
    if band:
        rows = [m for m in rows if m["band"] == band]
    correct = request.args.get("correct")
    if correct in ("0", "1"):
        rows = [m for m in rows if m["correct"] == (correct == "1")]

    # 매번 같은 순서로 보여주면 지루하므로 seed 로 섞되, 같은 seed 면 재현된다
    try:
        seed = int(request.args.get("seed", 0))
    except ValueError:
        seed = 0
    if seed:
        import random
        rows = rows[:]
        random.Random(seed).shuffle(rows)

    try:
        limit = max(1, min(60, int(request.args.get("limit", 12))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        limit, offset = 12, 0

    page = rows[offset:offset + limit]
    hit = sum(1 for m in rows if m["correct"])
    from collections import Counter
    vc = Counter(m["verdict"] for m in rows)
    return jsonify({
        "total": len(rows),
        "accuracy": round(hit / len(rows), 4) if rows else None,
        "summary": {
            "n": len(rows),
            "avg_win_prob_10min": (round(sum(m["win_prob_blue"] for m in rows) / len(rows), 4)
                                   if rows else None),
            "역전패": vc.get("역전패", 0), "초반 붕괴": vc.get("초반 붕괴", 0),
            "역전승": vc.get("역전승", 0), "리드 굳힘": vc.get("리드 굳힘", 0),
            "model_correct": hit,
        },
        "offset": offset,
        "returned": len(page),
        "matches": page,
        "note": "학습에 한 번도 쓰지 않은 시험셋 경기입니다. 틀린 판도 그대로 보여줍니다.",
    })


@app.route("/api/summoner", methods=["POST"])
def api_summoner():
    """Riot ID 로 최근 솔로랭크 경기들을 10분 시점에서 복기한다 (끝난 경기만 가능)."""
    if not RIOT_READY:
        # 키가 아예 없는 것과, 있는데 만료된 것은 다른 상황이다.
        # 뭉뚱그리면 "넣으라"는 안내를 받고 이미 넣은 사람이 혼란스러워진다.
        if os.environ.get("RIOT_API_KEY"):
            return jsonify({"error": "Riot API 키가 만료되어 소환사 조회를 일시 중단했습니다. "
                                     "(개발용 키는 24시간마다 만료됩니다) "
                                     "샘플 경기로는 모든 기능을 그대로 확인할 수 있습니다."}), 503
        return jsonify({"error": "서버에 Riot API 키가 없어 소환사 조회를 쓸 수 없습니다. "
                                 "샘플 경기로는 모든 기능을 그대로 확인할 수 있습니다."}), 503
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
