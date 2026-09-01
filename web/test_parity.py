# 서빙 파리티 테스트 — 화면에 뜨는 확률과 predict.py 의 확률이 같은지 기계로 검사한다
#
# 실행: 1) ./check_project.sh start   (서비스 켜기)
#       2) python web/test_parity.py
#
# 왜 필요한가: 웹에 예측 코드를 또 만들면 화면 확률과 모델 확률이 갈라져도 아무도 모른다.
# 이 테스트가 "두 계층이 같은 답을 낸다"를 증명한다.
#
# 검사 경로 세 가지가 전부 같아야 통과한다
#   predict.py 직접 호출  ==  백엔드 9524  ==  프론트엔드 9504 (프론트가 백엔드로 넘긴 결과)
import json
import os
import sys
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BACKEND_PORT, FRONTEND_PORT
from predict import _DEMOS, predict

FRONT_URL = f"http://127.0.0.1:{FRONTEND_PORT}/api/predict"
BACK_URL = f"http://127.0.0.1:{BACKEND_PORT}/api/predict"


def call(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main():
    print("서빙 파리티 테스트")
    print(f"  predict.py  vs  백엔드 {BACKEND_PORT}  vs  프론트엔드 {FRONTEND_PORT}\n")

    failures = 0
    for name, payload in _DEMOS:
        direct = predict(payload)
        try:
            back = call(BACK_URL, payload)
            front = call(FRONT_URL, payload)
        except urllib.error.URLError as e:
            print(f"[실패] 서비스에 연결할 수 없습니다: {e}")
            print("       먼저 ./check_project.sh start 를 실행하세요.")
            return 1

        def same(a, b):
            return (a["win_prob_blue"] == b["win_prob_blue"]
                    and a["pred"] == b["pred"]
                    and [f["feature"] for f in a["top_factors"]]
                    == [f["feature"] for f in b["top_factors"]])

        ok = same(direct, back) and same(direct, front)
        failures += 0 if ok else 1
        print(f"[{'통과' if ok else '실패'}] {name}")
        print(f"        predict.py {direct['win_prob_blue']:.4f} · "
              f"백엔드 {back['win_prob_blue']:.4f} · 프론트 {front['win_prob_blue']:.4f}")

    print()
    if failures:
        print(f"{failures}건 불일치 — 화면 확률과 모델 확률이 갈라졌습니다. 원인을 찾아야 합니다.")
        return 1
    print("전부 통과 — 화면에 뜨는 확률은 predict.py 의 확률과 완전히 같습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
