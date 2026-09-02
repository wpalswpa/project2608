"""산출물(모델·스키마) 경로와 적재.

경로를 한 곳에 모아 두는 이유: 지금까지 predict.py·web/·src/ 가 각자
os.path.join 으로 경로를 만들고 있었다. 한 곳만 바뀌어도 조용히 어긋난다.

모델은 처음 쓸 때 한 번만 읽고 메모리에 둔다(웹이 요청마다 읽으면 느리다).
"""
from __future__ import annotations

import json
import os

# 패키지 위치 기준으로 저장소 루트를 잡는다. 작업 디렉터리에 의존하지 않는다 —
# 라이브러리가 남의 프로그램 cwd 를 가정하면 안 되기 때문이다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS = os.path.join(ROOT, "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS, "model.joblib")
SCHEMA_PATH = os.path.join(ARTIFACTS, "schema.json")

_model = None
_schema = None


def load_schema(path: str | None = None) -> dict:
    """schema.json — 피처 목록과 학습 범위, 성능 기록."""
    global _schema
    if path is not None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if _schema is None:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            _schema = json.load(f)
    return _schema


def load_model(path: str | None = None):
    """학습된 Pipeline(StandardScaler + LogisticRegression) 을 통째로 읽는다."""
    global _model
    import joblib

    if path is not None:
        return joblib.load(path)
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"{MODEL_PATH} 가 없습니다 — python src/finalize_model.py 로 먼저 학습하세요")
        _model = joblib.load(MODEL_PATH)
    return _model


def reset_cache() -> None:
    """테스트에서 다른 모델을 읽고 싶을 때."""
    global _model, _schema
    _model = _schema = None


def describe() -> dict:
    """이 모델이 어디서 왔는지 — 발표·디버깅에서 제일 먼저 보는 정보."""
    s = load_schema()
    return {
        "model": s["model_name"], "version": s["version"],
        "time_point_min": s["time_point_min"], "target": s["target"],
        "feature_set": s["feature_set"], "trained_at": s["trained_at"],
        "data_source": s["data_source"], "sklearn_version": s["sklearn_version"],
        "seed": s["seed"], "metrics_holdout": s["metrics_holdout"],
        "n_features": len(s["features"]),
    }
