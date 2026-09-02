"""lolwin — LoL 10분 시점 승패 예측 라이브러리.

import 만으로는 아무 부작용도 없다 — 작업 디렉터리를 바꾸거나 모델을 읽지 않는다.
모델은 predict() 를 처음 부를 때 한 번만 읽어 메모리에 둔다.

    from lolwin import predict
    predict({"GoldDiff": 2000, "ExpDiff": 1500, ...})   # 13개 피처

피처를 바꾸려면 lolwin/features.py 만 고친다 — 거기가 유일한 정본이고,
SQL 뷰도 거기서 생성·대조한다.
"""
from lolwin.artifacts import describe, load_model, load_schema
from lolwin.features import DIFF13, KOREAN, TARGET, TIME_POINT_MIN
from lolwin.predict import predict, predict_batch

__all__ = [
    "predict", "predict_batch",
    "DIFF13", "KOREAN", "TARGET", "TIME_POINT_MIN",
    "describe", "load_model", "load_schema",
    "__version__",
]
__version__ = "1.0.0"
