# 학습 재현성 — lolwin.train() 이 지금 서비스 중인 모델을 그대로 다시 만드는가
#
# 실행: python tests/test_training_reproducible.py
#
# 왜 필요한가: "이 모델 어떻게 만들었어요?" 에 코드로 답할 수 있어야 한다.
# 학습 경로가 산출물과 어긋나면, 문서가 설명하는 모델과 서비스가 쓰는 모델이 다른 것이다.
#
# 원본 CSV 가 있어야 돌아간다(저장소에 없다 — data/README.md 참고).
# 없으면 건너뛴다. 데이터 있는 곳에서 한 번은 돌려야 의미가 있다.
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lolwin.data import CSV_PATH  # noqa: E402


def _skip_reason() -> str | None:
    if not os.path.exists(CSV_PATH):
        return f"원본 CSV 없음 ({os.path.relpath(CSV_PATH, ROOT)}) — 데이터 있는 환경에서 실행하세요"
    if not os.path.exists(os.path.join(ROOT, "artifacts", "model.joblib")):
        return "artifacts/model.joblib 없음"
    return None


def test_retraining_reproduces_shipped_model():
    """다시 학습해도 계수·절편·스케일러가 완전히 같아야 한다."""
    import joblib
    import numpy as np

    from lolwin.model import train

    with tempfile.TemporaryDirectory(prefix="lolwin_test_") as tmp:
        train(out_dir=tmp, verbose=False)
        new = joblib.load(os.path.join(tmp, "model.joblib"))

    old = joblib.load(os.path.join(ROOT, "artifacts", "model.joblib"))
    pairs = [
        ("계수", new.named_steps["model"].coef_, old.named_steps["model"].coef_),
        ("절편", new.named_steps["model"].intercept_, old.named_steps["model"].intercept_),
        ("스케일러 평균", new.named_steps["scaler"].mean_, old.named_steps["scaler"].mean_),
        ("스케일러 표준편차", new.named_steps["scaler"].scale_, old.named_steps["scaler"].scale_),
    ]
    bad = [name for name, a, b in pairs if not np.array_equal(a, b)]
    assert not bad, (f"재학습 결과가 서비스 중인 모델과 다릅니다: {', '.join(bad)}. "
                     "학습 경로나 데이터가 바뀌었습니다.")


def test_schema_matches_shipped():
    """재학습이 만든 schema 가 배포본과 같아야 한다 — 성능과 피처 규격 둘 다.

    성능만 보면 피처 type·범위가 어긋나도 통과한다. 실제로 AvgLevelDiff 가
    float 인데 int 로 적히는 버그를 이 검사가 없어서 놓쳤다.
    """
    import json

    from lolwin.model import train

    with tempfile.TemporaryDirectory(prefix="lolwin_test_") as tmp:
        got = train(out_dir=tmp, verbose=False)["schema"]

    with open(os.path.join(ROOT, "artifacts", "schema.json"), encoding="utf-8") as f:
        shipped = json.load(f)

    bad = []
    for k, v in shipped["metrics_holdout"].items():
        if got["metrics_holdout"].get(k) != v:
            bad.append(f"성능 {k}: {v} → {got['metrics_holdout'].get(k)}")

    for feat, spec in shipped["features"].items():
        for field, want in spec.items():
            have = got["features"].get(feat, {}).get(field)
            if have != want:
                bad.append(f"피처 {feat}.{field}: {want} → {have}")

    # 재학습해도 바뀌면 안 되는 정체성 항목 (trained_at·provenance 는 당연히 바뀐다)
    for k in ("model_name", "version", "time_point_min", "target",
              "feature_set", "seed", "sklearn_version"):
        if got.get(k) != shipped.get(k):
            bad.append(f"{k}: {shipped.get(k)} → {got.get(k)}")

    assert not bad, "배포본과 달라졌습니다:\n  " + "\n  ".join(bad)


def main():
    reason = _skip_reason()
    if reason:
        print(f"[건너뜀] {reason}")
        return 0

    failed = 0
    for t in (test_retraining_reproduces_shipped_model, test_schema_matches_shipped):
        try:
            t()
            print(f"[통과] {t.__name__} — {t.__doc__.splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"[실패] {t.__name__}\n  {e}")
    print()
    print("학습 경로가 서비스 중인 모델을 그대로 재현합니다." if not failed
          else f"{failed}건 실패 — 학습 경로와 산출물이 어긋났습니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
