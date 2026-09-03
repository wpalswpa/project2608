# 코칭 검증 — 조언이 엉터리로 뒤집히지 않는가
#
# 실행: python tests/test_coach.py
#
# 이 검사가 존재하는 이유: 계수를 그대로 쓰면 KillsDiff(-0.107)·
# TotalMinionsKilledDiff(-0.157) 때문에 "킬하지 마라 · CS 먹지 마라" 라는
# 조언이 나온다. 화면에 그대로 나가면 프로젝트 전체의 신뢰가 무너진다.
# 그래서 "더 잘하면 승률이 오른다" 는 당연한 성질을 기계가 지키는지 본다.
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lolwin.coach import COACH_STEP, GOLD_PER_UNIT, advise, verdict_advice  # noqa: E402
from lolwin.features import DIFF13  # noqa: E402

# 불리하게 시작한 판 — 조언이 의미 있으려면 개선 여지가 있어야 한다
LOSING = {f: 0.0 for f in DIFF13}
LOSING.update({"GoldDiff": -800, "TotalMinionsKilledDiff": -20, "KillsDiff": -2})


def test_advice_never_says_do_worse():
    """모든 조언이 승률을 올려야 한다 — 이게 깨지면 '킬하지 마라'가 나온다."""
    r = advise(LOSING, top_n=len(COACH_STEP))
    bad = [f"{a['name']}: {a['gain']:+.4f}" for a in r["actions"] if a["gain"] <= 0]
    assert not bad, ("더 잘하면 승률이 내려간다고 말하고 있습니다: " + ", ".join(bad) +
                     " — 따라오는 골드를 함께 반영했는지 확인하세요(다중공선성).")


def test_naive_version_would_fail():
    """골드를 함께 올리지 않으면 실제로 뒤집히는지 확인한다.

    위 검사가 '항상 통과하는 무의미한 검사'가 아님을 증명하는 검사다.
    과거에 아무것도 못 잡는 규칙을 만든 적이 있어 반대 방향도 함께 본다.
    """
    from lolwin.predict import predict

    base = predict(LOSING)["win_prob_blue"]
    naive = dict(LOSING)
    naive["TotalMinionsKilledDiff"] += 20        # 골드는 그대로 둔다 (현실에 없는 상황)
    assert predict(naive)["win_prob_blue"] < base, (
        "골드를 안 올렸는데도 승률이 올랐습니다 — 계수가 바뀌었다면 "
        "coach.py 의 전제(다중공선성 보정)를 다시 확인하세요.")


def test_actions_sorted_by_gain():
    """상승폭이 큰 순서여야 한다 — 감독은 가장 효과적인 것부터 말한다."""
    gains = [a["gain"] for a in advise(LOSING, top_n=len(COACH_STEP))["actions"]]
    assert gains == sorted(gains, reverse=True), f"정렬이 깨졌습니다: {gains}"


def test_gold_per_unit_matches_training_data():
    """GOLD_PER_UNIT 이 학습 데이터에서 다시 재도 같은 값인가.

    코드에 박힌 상수가 근거와 어긋나면 조언의 크기가 조용히 틀어진다.
    데이터가 없는 환경에서는 건너뛴다.
    """
    try:
        import numpy as np

        from lolwin.data import CSV_PATH, load
    except Exception:
        print("  [건너뜀] 의존성 없음")
        return
    if not os.path.exists(CSV_PATH):
        print("  [건너뜀] 원본 CSV 없음")
        return

    X, _, _, _, _ = load(source="csv")
    bad = []
    for name, want in GOLD_PER_UNIT.items():
        got = float(np.polyfit(X[name], X["GoldDiff"], 1)[0])
        if abs(got - want) > 0.5:
            bad.append(f"{name}: 코드 {want} vs 실측 {got:.1f}")
    assert not bad, "GOLD_PER_UNIT 이 데이터와 다릅니다:\n  " + "\n  ".join(bad)


def test_verdict_advice_covers_all_four():
    """네 갈래 판정 전부 처방이 있어야 한다."""
    for v in ("우세승", "역전승", "역전패", "열세패"):
        a = verdict_advice(v)
        assert a["headline"] and a["detail"], f"{v} 처방이 비어 있습니다"


def main():
    tests = [test_advice_never_says_do_worse, test_naive_version_would_fail,
             test_actions_sorted_by_gain, test_gold_per_unit_matches_training_data,
             test_verdict_advice_covers_all_four]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[통과] {t.__name__} — {t.__doc__.splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"[실패] {t.__name__}\n  {e}")
    print()
    print("조언이 사용자를 잘못된 방향으로 이끌지 않습니다." if not failed
          else f"{failed}건 실패 — 조언이 틀렸습니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
