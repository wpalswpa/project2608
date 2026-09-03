# predict.py — 예측 진입점 (CLI + 기존 호출 호환용 얇은 껍데기)
#
# 실제 로직은 lolwin/predict.py 에 있다. 이 파일은 두 가지만 한다:
#   ① 명령행에서 바로 써 볼 수 있게 하고
#   ② `from predict import predict` 로 쓰던 기존 코드(web/, src/riot_api.py)를 그대로 돌게 한다
#
# 사용 (함수):
#   from lolwin import predict          # 새 코드는 이쪽을 쓸 것
#   from predict import predict         # 기존 코드 — 계속 동작한다
#
# 사용 (명령행):
#   python predict.py --demo                      # 예시 3건 실행
#   python predict.py '{"GoldDiff": 2000, ...}'   # JSON 직접 입력
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lolwin.artifacts import MODEL_PATH as _MODEL_PATH  # noqa: F401  (기존 import 호환)
from lolwin.artifacts import SCHEMA_PATH as _SCHEMA_PATH  # noqa: F401
from lolwin.features import KOREAN as _KOREAN  # noqa: F401
from lolwin.predict import DEMOS as _DEMOS  # noqa: F401
from lolwin.predict import predict, predict_batch  # noqa: F401

__all__ = ["predict", "predict_batch", "_DEMOS", "_KOREAN", "_SCHEMA_PATH", "_MODEL_PATH"]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] != "--demo":
        cases = [("입력", json.loads(sys.argv[1]))]
    else:
        cases = _DEMOS
    for name, payload in cases:
        r = predict(payload)
        print(f"\n=== {name} ===")
        print(f"  블루 승리 확률 {r['win_prob_blue']:.1%} → {r['pred_label']}")
        for tf in r["top_factors"][:3]:
            print(f"  · {tf['name']} = {tf['value']} ({tf['direction']}, 기여 {tf['contribution']:+.3f})")
        for w in r["warnings"]:
            print(f"  ⚠ {w}")
