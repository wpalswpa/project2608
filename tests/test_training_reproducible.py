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


def test_metrics_match_schema():
    """재학습 성능이 schema.json 에 적힌 값과 같아야 한다."""
    import json

    from lolwin.model import train

    with tempfile.TemporaryDirectory(prefix="lolwin_test_") as tmp:
        r = train(out_dir=tmp, verbose=False)

    with open(os.path.join(ROOT, "artifacts", "schema.json"), encoding="utf-8") as f:
        shipped = json.load(f)["metrics_holdout"]

    bad = [f"{k}: {shipped[k]} → {r['metrics'][k]}"
           for k in shipped if r["metrics"].get(k) != shipped[k]]
    assert not bad, "성능이 달라졌습니다:\n  " + "\n  ".join(bad)


def main():
    reason = _skip_reason()
    if reason:
        print(f"[건너뜀] {reason}")
        return 0

    failed = 0
    for t in (test_retraining_reproduces_shipped_model, test_metrics_match_schema):
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
