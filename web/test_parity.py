# 서빙 파리티 테스트 — 웹 화면의 확률과 predict.py 의 확률이 같은지 기계적으로 검사
#
# 실행: 1) 다른 창에서  python web/app.py   (서버 켜기)
#       2) python web/test_parity.py
#
# 왜 필요한가: 웹에 예측 로직을 또 짜면 화면 확률과 predict.py 확률이 갈라져도
# 아무도 모른다. 이 테스트가 "두 계층이 같은 답을 낸다"를 증명한다. (spec 002 품질 요구)
import json
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("web", 1)[0])
from predict import _DEMOS, predict

URL = "http://localhost:5000/api/predict"


def call_api(payload: dict) -> dict:
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    print("서빙 파리티 테스트 — 웹 API vs predict.py 직접 호출\n")
    for name, payload in _DEMOS:
        direct = predict(payload)
        try:
            api = call_api(payload)
        except Exception as e:
            print(f"[실패] 서버에 연결할 수 없습니다: {e}")
            print("       먼저 다른 창에서 'python web/app.py' 를 실행하세요.")
            return 1
        same_prob = direct["win_prob_blue"] == api["win_prob_blue"]
        same_pred = direct["pred"] == api["pred"]
        same_top = [f["feature"] for f in direct["top_factors"]] == \
                   [f["feature"] for f in api["top_factors"]]
        ok = same_prob and same_pred and same_top
        print(f"[{'통과' if ok else '실패'}] {name}: "
              f"직접 {direct['win_prob_blue']:.4f} / API {api['win_prob_blue']:.4f} "
              f"· 예측 {direct['pred']}=={api['pred']} · 요인순서 {'일치' if same_top else '불일치'}")
        assert ok, f"파리티 위반: {name}"
    print("\n전부 통과 — 화면에 뜨는 확률은 predict.py 의 확률과 동일합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
