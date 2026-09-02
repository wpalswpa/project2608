# 회귀 테스트용 정답지(golden) 생성 — 리팩터링 전에 "지금 모델이 뭐라고 답하는지" 를 박제한다.
#
# 실행: python tests/make_golden.py
#
# 왜 필요한가: 라이브러리로 구조를 바꾸는 동안 예측값이 1비트라도 달라지면 안 된다.
# 그런데 눈으로는 확인이 안 된다. 그래서 지금 값을 파일로 고정해 두고,
# 구조를 바꿀 때마다 tests/test_regression.py 로 대조한다.
#
# 입력은 schema.json 의 학습 범위 안에서 시드 고정으로 만든다.
# 데이터 CSV 없이 artifacts/ 만으로 돌아가야 하기 때문이다(CSV 는 저장소에 없다).
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from predict import predict  # noqa: E402  (경로 세팅 후 import)

SEED = 20260902
N = 50
OUT = os.path.join(ROOT, "tests", "golden_predictions.json")


def make_inputs():
    """schema 의 train_min~train_max 안에서 골고루 뽑는다. 정수 피처는 정수로."""
    with open(os.path.join(ROOT, "artifacts", "schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    rng = np.random.default_rng(SEED)
    rows = []
    for _ in range(N):
        row = {}
        for name, spec in schema["features"].items():
            lo, hi = spec["train_min"], spec["train_max"]
            v = rng.uniform(lo, hi)
            # 원본이 정수인 피처는 정수로 (AvgLevelDiff 만 소수)
            row[name] = round(float(v), 2) if name == "AvgLevelDiff" else int(round(v))
        rows.append(row)
    return schema, rows


def main():
    schema, rows = make_inputs()
    cases = []
    for row in rows:
        r = predict(row)
        cases.append({
            "input": row,
            "expected": {
                # 반올림된 값이 아니라 원본 그대로 비교해야 미세한 변화도 잡힌다
                "win_prob_blue": r["win_prob_blue"],
                "pred": r["pred"],
                "top_factors": [
                    {"feature": f["feature"], "contribution": f["contribution"]}
                    for f in r["top_factors"]
                ],
                "n_warnings": len(r["warnings"]),
            },
        })

    payload = {
        "생성기준": {
            "seed": SEED,
            "건수": len(cases),
            "model_version": schema["version"],
            "trained_at": schema["trained_at"],
            "sklearn_version": schema["sklearn_version"],
        },
        "설명": "리팩터링 전후로 예측이 완전히 같은지 확인하는 정답지. "
                "모델을 재학습했다면 이 파일도 다시 만들어야 한다.",
        "cases": cases,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    probs = [c["expected"]["win_prob_blue"] for c in cases]
    print(f"[생성] {os.path.relpath(OUT, ROOT)}  {len(cases)}건")
    print(f"  확률 범위 {min(probs):.4f} ~ {max(probs):.4f}")
    print(f"  블루 승 예측 {sum(c['expected']['pred'] for c in cases)}건")
    print(f"  모델 {schema['version']} · 학습 {schema['trained_at']}")


if __name__ == "__main__":
    main()
