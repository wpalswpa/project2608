"""예측 — 이 프로젝트에서 확률을 계산하는 유일한 곳.

웹·CLI·노트북이 전부 이 함수를 부른다. 계산이 두 곳에 있으면
화면 확률과 모델 확률이 갈라져도 아무도 모르기 때문이다(서빙 파리티).

계산은 세 줄로 끝난다:
    z    = (입력 - 평균) / 표준편차        표준화
    로짓  = 계수 · z + 절편                선형합
    확률  = 1 / (1 + exp(-로짓))           시그모이드
"""
from __future__ import annotations

from lolwin.artifacts import load_model, load_schema
from lolwin.features import DIFF13, KOREAN

TOP_N = 5
"""승리요인으로 돌려줄 개수."""


def predict(payload: dict) -> dict:
    """경기 상태(13개 차이 피처) → 승리 확률·예측·승리요인·경고.

    반환:
      win_prob_blue  블루팀 승리 확률 (0~1, 소수 4자리)
      pred           1=블루 승 예측, 0=레드 승 예측
      top_factors    이 판의 예측을 움직인 요인 상위 5 (기여도 절대값 내림차순)
      warnings       학습 범위 밖 입력 등 주의사항 (비면 안심)
      meta           모델 버전·시점·홀드아웃 성능

    빠진 피처가 있으면 ValueError. 범위 밖 값은 막지 않고 warnings 에 담는다 —
    막아버리면 이례적인 경기를 아예 못 보기 때문이다.
    """
    import numpy as np
    import pandas as pd

    model = load_model()
    schema = load_schema()
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
    order = np.argsort(-np.abs(contrib))[:TOP_N]
    top_factors = [{
        "feature": features[i],
        "name": KOREAN.get(features[i], features[i]),
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


def predict_batch(rows: list[dict]) -> list[dict]:
    """여러 경기를 한 번에. 하나라도 입력이 잘못되면 그 건에서 ValueError."""
    return [predict(r) for r in rows]


DEMOS = [
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
