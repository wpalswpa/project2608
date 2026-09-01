# predict.py — LoL 승패 예측·설명 서비스의 예측 진입점 (산출물 6종 중 하나)
#
# 예측 로직의 단일 진실(single source of truth). 웹 등 다른 계층은 이 결과를
# 보여주기만 하며, 서빙 파리티 테스트로 이 파일과의 일치를 검증한다.
#
# 사용 (함수):
#   from predict import predict
#   result = predict({"GoldDiff": 2000, "ExpDiff": 1200, ...})   # 13개 피처
#
# 사용 (명령행):
#   python predict.py --demo                      # 예시 3건 실행
#   python predict.py '{"GoldDiff": 2000, ...}'   # JSON 직접 입력
#
# 입력: schema.json 의 13개 차이 피처(블루-레드, 양수=블루 우세).
#       빠진 값이 있으면 에러, 학습 범위 밖이면 경고를 담아 반환한다.
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_PATH = os.path.join(_DIR, "artifacts", "model.joblib")
_SCHEMA_PATH = os.path.join(_DIR, "artifacts", "schema.json")

# 피처 → 사람이 읽는 이름 (승리요인 설명용)
_KOREAN = {
    "GoldDiff": "골드(돈) 차이", "ExpDiff": "경험치 차이", "KillsDiff": "킬 차이",
    "FirstBlood": "첫 킬", "WardsPlacedDiff": "와드 설치 차이",
    "WardsDestroyedDiff": "와드 제거 차이", "AssistsDiff": "어시스트 차이",
    "DragonsDiff": "드래곤 차이", "HeraldsDiff": "전령 차이",
    "TowersDestroyedDiff": "타워 파괴 차이", "AvgLevelDiff": "평균 레벨 차이",
    "TotalMinionsKilledDiff": "미니언(CS) 차이",
    "TotalJungleMinionsKilledDiff": "정글 몬스터 차이",
}

_model = None
_schema = None


def _load():
    global _model, _schema
    if _model is None:
        _model = joblib.load(_MODEL_PATH)
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            _schema = json.load(f)
    return _model, _schema


def predict(payload: dict) -> dict:
    """경기 상태(13개 차이 피처) → 승리 확률·예측·승리요인·경고.

    반환 dict:
      win_prob_blue  블루팀 승리 확률 (0~1)
      pred           1=블루 승 예측, 0=레드 승 예측
      top_factors    이 판의 예측을 움직인 요인 상위 5 (기여도 내림차순)
      warnings       학습 범위 밖 입력 등 주의사항 (비면 안심)
      meta           모델 버전·시점·홀드아웃 성능
    """
    model, schema = _load()
    features = list(schema["features"].keys())

    missing = [f for f in features if f not in payload]
    if missing:
        raise ValueError(f"입력에 빠진 피처 {len(missing)}개: {missing}")

    X = pd.DataFrame([{f: payload[f] for f in features}])[features]

    warnings = []
    for f in features:
        lo, hi = schema["features"][f]["train_min"], schema["features"][f]["train_max"]
        v = float(X[f].iloc[0])
        if not (lo <= v <= hi):
            warnings.append(f"{f}={v} 가 학습 범위 [{lo}, {hi}] 밖 — 예측을 믿지 마세요")

    prob = float(model.predict_proba(X)[0, 1])
    pred = int(prob >= 0.5)

    # 승리요인: 표준화 좌표에서의 기여도 = 계수 × z값 (로지스틱 선형항 분해)
    #
    # ⚠️ 해석 주의: 이 기여도는 "다른 피처를 통제한 뒤" 값이다. 특히 KillsDiff 는
    # 킬로 번 돈이 이미 GoldDiff 에 들어 있어(상관 +0.92) 기여도가 음수로 나올 수 있다.
    # "킬을 하면 진다"는 뜻이 아니라 "골드를 본 뒤엔 킬이 더 보탤 정보가 없다"는 뜻.
    # 화면에 그대로 노출할 때는 이 설명을 함께 보여줄 것 (model_card.md 승리요인 항목).
    scaler = model.named_steps["scaler"]
    coefs = model.named_steps["model"].coef_[0]
    z = (X.values[0] - scaler.mean_) / scaler.scale_
    contrib = coefs * z
    order = np.argsort(-np.abs(contrib))[:5]
    top_factors = [{
        "feature": features[i],
        "name": _KOREAN.get(features[i], features[i]),
        "value": float(X.iloc[0, i]),
        "contribution": round(float(contrib[i]), 4),
        "direction": "블루에 유리" if contrib[i] > 0 else "레드에 유리",
    } for i in order]

    return {
        "win_prob_blue": round(prob, 4),
        "pred": pred,
        "pred_label": "블루 승리 예측" if pred else "레드 승리 예측",
        "top_factors": top_factors,
        "warnings": warnings,
        "meta": {
            "model": schema["model_name"], "version": schema["version"],
            "time_point_min": schema["time_point_min"],
            "holdout_accuracy": schema["metrics_holdout"]["accuracy"],
        },
    }


_DEMOS = [
    ("팽팽한 접전", dict(FirstBlood=1, KillsDiff=0, GoldDiff=150, ExpDiff=-100,
                    WardsPlacedDiff=2, WardsDestroyedDiff=0, AssistsDiff=1,
                    DragonsDiff=0, HeraldsDiff=0, TowersDestroyedDiff=0,
                    AvgLevelDiff=0.0, TotalMinionsKilledDiff=5,
                    TotalJungleMinionsKilledDiff=-2)),
    ("블루가 크게 우세", dict(FirstBlood=1, KillsDiff=5, GoldDiff=4500, ExpDiff=3000,
                       WardsPlacedDiff=5, WardsDestroyedDiff=2, AssistsDiff=6,
                       DragonsDiff=1, HeraldsDiff=1, TowersDestroyedDiff=1,
                       AvgLevelDiff=1.2, TotalMinionsKilledDiff=30,
                       TotalJungleMinionsKilledDiff=10)),
    ("레드가 우세", dict(FirstBlood=0, KillsDiff=-3, GoldDiff=-2200, ExpDiff=-1500,
                    WardsPlacedDiff=-1, WardsDestroyedDiff=-1, AssistsDiff=-4,
                    DragonsDiff=-1, HeraldsDiff=0, TowersDestroyedDiff=0,
                    AvgLevelDiff=-0.6, TotalMinionsKilledDiff=-15,
                    TotalJungleMinionsKilledDiff=-5)),
]

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
