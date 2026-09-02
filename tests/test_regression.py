# 회귀 테스트 — 구조를 바꿔도 예측이 그대로인가
#
# 실행: python tests/test_regression.py     (pytest 없이도 돈다)
#       pytest tests/test_regression.py     (pytest 가 있으면 이렇게도)
#
# 라이브러리로 옮기는 각 단계마다 이걸 돌린다. 하나라도 어긋나면 그 단계를 되돌린다.
# 정답지는 tests/make_golden.py 로 만든다 — 모델을 재학습했을 때만 다시 만들 것.
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GOLDEN = os.path.join(ROOT, "tests", "golden_predictions.json")


def _load():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


def test_predictions_unchanged():
    """확률·예측·요인 순서가 정답지와 완전히 같아야 한다."""
    from predict import predict

    data = _load()
    bad = []
    for i, case in enumerate(data["cases"]):
        got = predict(case["input"])
        exp = case["expected"]

        if got["win_prob_blue"] != exp["win_prob_blue"]:
            bad.append(f"[{i}] 확률 {exp['win_prob_blue']} → {got['win_prob_blue']}")
            continue
        if got["pred"] != exp["pred"]:
            bad.append(f"[{i}] 예측 {exp['pred']} → {got['pred']}")
            continue

        got_f = [(f["feature"], f["contribution"]) for f in got["top_factors"]]
        exp_f = [(f["feature"], f["contribution"]) for f in exp["top_factors"]]
        if got_f != exp_f:
            bad.append(f"[{i}] 승리요인 바뀜{chr(10)}    이전 {exp_f}{chr(10)}    지금 {got_f}")
            continue
        if len(got["warnings"]) != exp["n_warnings"]:
            bad.append(f"[{i}] 경고 개수 {exp['n_warnings']} → {len(got['warnings'])}")

    assert not bad, (f"{len(bad)}건이 정답지와 다릅니다:" + chr(10)
                     + chr(10).join("  " + b for b in bad[:10]))


def test_model_identity_unchanged():
    """모델 파일 자체가 바뀌지 않았는지 — 바뀌었다면 정답지부터 다시 만들어야 한다."""
    import json as _json

    with open(os.path.join(ROOT, "artifacts", "schema.json"), encoding="utf-8") as f:
        schema = _json.load(f)
    meta = _load()["생성기준"]
    assert schema["version"] == meta["model_version"], (
        f"모델 버전이 {meta['model_version']} → {schema['version']} 로 바뀌었습니다. "
        "재학습했다면 python tests/make_golden.py 로 정답지를 다시 만드세요.")
    assert schema["trained_at"] == meta["trained_at"], (
        f"학습 시각이 다릅니다 ({meta['trained_at']} → {schema['trained_at']}). "
        "재학습했다면 정답지를 다시 만드세요.")


def main():
    tests = [test_model_identity_unchanged, test_predictions_unchanged]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[통과] {t.__name__} — {t.__doc__.splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"[실패] {t.__name__}{chr(10)}  {e}")
    print()
    if failed:
        print(f"{failed}건 실패 — 구조 변경이 예측을 바꿨습니다. 되돌리세요.")
        return 1
    n = len(_load()["cases"])
    print(f"전부 통과 — 예측 {n}건이 정답지와 완전히 같습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
