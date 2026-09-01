# API 스모크 테스트 — 프런트(9504)를 통해 모든 엔드포인트가 살아 있고 형태가 맞는지 확인
# 실행: ./check_project.sh test   또는  python web/test_api.py
import json
import os
import sys
import urllib.request

PORT = int(os.environ.get("FRONTEND_PORT", 9504))
BASE = os.environ.get("BASE_URL", f"http://127.0.0.1:{PORT}")


def get(path, data=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    fails = 0
    def check(name, cond, extra=""):
        nonlocal fails
        print(f"[{'통과' if cond else '실패'}] {name} {extra}")
        fails += 0 if cond else 1
    st, h = get("/healthz");            check("GET /healthz", st == 200 and h["backend_ok"], f"→ backend_ok={h.get('backend_ok')}")
    st, h = get("/api/health");         check("GET /api/health", st == 200 and h["status"] == "ok" and h["parity"]["passed"], f"→ 모델 {h['model']['name']} v{h['model']['version']} 홀드아웃 {h['model']['holdout_accuracy']}")
    st, s = get("/api/schema");         check("GET /api/schema", st == 200 and len(s["features"]) == 13, f"→ 피처 {len(s.get('features', {}))}개")
    st, ex = get("/api/examples");      check("GET /api/examples", st == 200 and len(ex) == 3)
    st, p = get("/api/predict", ex[1]["payload"]); check("POST /api/predict (블루 우세)", st == 200 and p["pred"] == 1 and len(p["top_factors"]) == 5, f"→ {p.get('win_prob_blue')}")
    st, b = get("/api/predict/batch", [e["payload"] for e in ex]); check("POST /api/predict/batch", st == 200 and len(b) == 3 and b[1]["win_prob_blue"] == p["win_prob_blue"])
    st, e = get("/api/predict", {"GoldDiff": 100}); check("POST /api/predict 누락 피처 → 400", st == 400 and "빠진" in e.get("error", ""))
    st, w = get("/api/predict", {**ex[0]["payload"], "GoldDiff": 99999}); check("POST /api/predict 범위 밖 → 200+경고", st == 200 and w["warnings"])
    st, r = get("/api/report");         check("GET /api/report", st == 200 and r["errors"]["bins"] and r["win_factors"], f"→ 최약 구간 {r['errors'].get('weakest_bin')}")
    st, m = get("/api/match-types");    check("GET /api/match-types", st == 200 and m["k"] == 4, "→ " + " · ".join(f"{t['label']} {t['share_pct']}%" for t in m.get("types", [])))
    st, _ = get("/api/nope");           check("GET /api/nope → 404", st == 404)
    print("\n" + ("전부 통과" if not fails else f"{fails}건 실패"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
