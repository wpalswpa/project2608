# 서빙 계약 검사 — docs/serving.md 에 적은 약속을 코드가 지키는가
#
# 실행: python tests/test_contract.py     (서버 없이, 라이브러리만으로 돈다)
#
# 왜 필요한가: 계약이 문서에만 있으면 코드가 조용히 어긋난다.
# 여기서 막히면 docs/serving.md 를 고칠지, 코드를 고칠지 먼저 정해야 한다.
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lolwin import DIFF13, predict  # noqa: E402
from lolwin.artifacts import load_schema  # noqa: E402

OK = dict(FirstBlood=1, KillsDiff=3, GoldDiff=2000, ExpDiff=1500,
          WardsPlacedDiff=2, WardsDestroyedDiff=1, AssistsDiff=4,
          DragonsDiff=1, HeraldsDiff=0, TowersDestroyedDiff=0,
          AvgLevelDiff=0.4, TotalMinionsKilledDiff=15,
          TotalJungleMinionsKilledDiff=5)


def test_output_shape():
    """출력 필드와 형이 계약대로인가."""
    r = predict(OK)
    for k in ("win_prob_blue", "pred", "pred_label", "top_factors", "warnings", "meta"):
        assert k in r, f"{k} 가 없습니다"
    assert 0.0 <= r["win_prob_blue"] <= 1.0, "확률이 0~1 밖"
    assert round(r["win_prob_blue"], 4) == r["win_prob_blue"], "소수 4자리 반올림이 아님"
    assert r["pred"] in (0, 1), "pred 는 0 또는 1"
    assert isinstance(r["warnings"], list), "warnings 는 목록"


def test_pred_matches_threshold():
    """pred 는 확률 0.5 기준으로 갈려야 한다."""
    for payload in (OK, {**OK, "GoldDiff": -5000, "ExpDiff": -4000}):
        r = predict(payload)
        assert r["pred"] == int(r["win_prob_blue"] >= 0.5), (
            f"확률 {r['win_prob_blue']} 인데 pred={r['pred']}")


def test_top_factors():
    """정확히 5개, 기여도 절대값 내림차순."""
    f = predict(OK)["top_factors"]
    assert len(f) == 5, f"5개여야 하는데 {len(f)}개"
    mags = [abs(x["contribution"]) for x in f]
    assert mags == sorted(mags, reverse=True), f"내림차순이 아님: {mags}"
    for x in f:
        assert set(x) == {"feature", "name", "value", "contribution", "direction"}
        assert x["feature"] in DIFF13, f"모르는 피처 {x['feature']}"
        want = "블루에 유리" if x["contribution"] > 0 else "레드에 유리"
        assert x["direction"] == want, f"{x['feature']} 방향 표기가 기여도와 안 맞음"


def test_missing_feature_raises():
    """피처가 빠지면 ValueError — 조용히 0으로 채우면 안 된다."""
    bad = {k: v for k, v in OK.items() if k != "GoldDiff"}
    try:
        predict(bad)
    except ValueError as e:
        assert "GoldDiff" in str(e), f"빠진 피처 이름이 메시지에 없음: {e}"
        return
    raise AssertionError("피처가 빠졌는데 예외가 안 났습니다")


def test_out_of_range_warns_but_returns():
    """범위를 벗어나도 막지 않고 경고만 — 이례적인 경기를 못 보게 하지 않기 위해."""
    schema = load_schema()
    hi = schema["features"]["GoldDiff"]["train_max"]
    r = predict({**OK, "GoldDiff": hi + 10_000})
    assert r["warnings"], "범위 밖인데 경고가 없습니다"
    assert any("GoldDiff" in w for w in r["warnings"]), "어느 피처가 문제인지 안 알려줌"
    assert 0.0 <= r["win_prob_blue"] <= 1.0, "경고 상황에서도 확률은 나와야 함"


def test_in_range_no_warning():
    """정상 입력에는 경고가 없어야 한다 (경고가 늘 뜨면 아무도 안 본다)."""
    assert predict(OK)["warnings"] == [], "정상 입력인데 경고가 붙었습니다"


def test_schema_matches_features():
    """schema.json 의 피처 목록과 lolwin.features 의 정본이 같은가."""
    assert list(load_schema()["features"].keys()) == DIFF13, (
        "schema.json 과 lolwin/features.py 의 피처가 다릅니다 — 재학습이 필요합니다")


def test_csv_keeps_text_columns_as_text():
    """CSV 를 읽을 때 이름·태그를 숫자로 바꾸면 안 된다.

    Riot 태그 "0223" 을 int 로 읽으면 223 이 되어 앞자리 0 이 사라지고,
    화면의 "이름#태그" 링크가 존재하지 않는 계정을 가리킨다(실제로 그랬다).
    """
    import sys as _sys

    _sys.path.insert(0, os.path.join(ROOT, "web"))
    from app import _csv

    rows = _csv("champion_top_players.csv")
    if not rows:
        print("  [건너뜀] champion_top_players.csv 없음")
        return
    bad = [r for r in rows if not isinstance(r.get("tag"), str)
           or not isinstance(r.get("name"), str)]
    assert not bad, (f"이름·태그가 문자열이 아닙니다 ({len(bad)}건): "
                     f"{[(r.get('name'), r.get('tag')) for r in bad[:3]]} — "
                     "web/app.py 의 TEXT_COLUMNS 를 확인하세요.")
    # 숫자 열은 여전히 숫자여야 한다 (예외를 너무 넓게 걸지 않았는지)
    assert isinstance(rows[0].get("판수"), int), "숫자 열까지 문자열이 됐습니다"


def main():
    tests = [test_schema_matches_features, test_output_shape, test_pred_matches_threshold,
             test_top_factors, test_missing_feature_raises,
             test_out_of_range_warns_but_returns, test_in_range_no_warning,
             test_csv_keeps_text_columns_as_text]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"[통과] {t.__doc__.splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"[실패] {t.__name__}\n  {e}")
    print()
    print("계약 전부 통과 — docs/serving.md 대로 동작합니다." if not failed
          else f"{failed}건 실패 — 코드와 docs/serving.md 중 무엇이 맞는지 먼저 정하세요.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
