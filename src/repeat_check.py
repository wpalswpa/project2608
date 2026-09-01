# 반복 검증 — 시드를 바꿔 10번 다시 학습한다
#
# 실행: 프로젝트 폴더에서  python src/repeat_check.py
#
# 왜 필요한가: 지금까지 결과는 전부 "시드 42" 하나로 나온 값이다.
# 데이터를 어떻게 나누느냐(분할)에 따라 점수는 조금씩 흔들리는데,
# 한 번만 재고 "정확도 0.7136"이라고 하면 그게 실력인지 운인지 알 수 없다.
# 시드를 10개 바꿔 분할부터 다시 하고, 결과가 얼마나 흔들리는지 본다.
#
# 확인하는 것 3가지
#   1) 성능이 시드마다 얼마나 달라지나 (실험 A)
#   2) 승리요인 순위가 그대로 유지되나 (해석의 안정성)
#   3) "5분 더 보면 좋아진다"가 시드마다 일관되나 (실험 B)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)


import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from finalize_model import DIFF13, build_diff13_from_csv
from timepoint_compare import FEATURES as EXPB_FEATURES
from timepoint_compare import build as build_expb

SEEDS = [42, 0, 1, 7, 13, 21, 77, 100, 202, 777]   # 10개


def pipe(seed):
    return Pipeline([("scaler", StandardScaler()),
                     ("model", LogisticRegression(max_iter=1000, random_state=seed))])


def experiment_a():
    """실험 A — 다이아 랭크 10분. 시드마다 분할부터 다시 한다."""
    print("=" * 66)
    print("실험 A 반복 — 다이아 랭크 9,879판, 시드 10개")
    print("=" * 66)
    df = pd.read_csv("data/high_diamond_ranked_10min.csv").sort_values("gameId")
    X, y = build_diff13_from_csv(df), df["blueWins"]

    rows, coef_ranks = [], []
    for s in SEEDS:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=s, stratify=y)
        m = pipe(s).fit(X_tr, y_tr)
        proba = m.predict_proba(X_te)[:, 1]
        pred = (proba >= 0.5).astype(int)
        rows.append({"seed": s,
                     "정확도": accuracy_score(y_te, pred),
                     "F1": f1_score(y_te, pred),
                     "AUC": roc_auc_score(y_te, proba)})
        c = pd.Series(m.named_steps["model"].coef_[0], index=DIFF13)
        coef_ranks.append(c.abs().rank(ascending=False))

        # 접전 구간(골드차 1,000 미만) 정확도도 같이 본다
        close = X_te["GoldDiff"].abs() < 1000
        rows[-1]["접전정확도"] = accuracy_score(y_te[close], pred[close])
        rows[-1]["접전비중"] = close.mean()

    res = pd.DataFrame(rows).set_index("seed")
    print(res.round(4).to_string())
    print("\n[요약] 10회 반복 결과")
    for c in ["정확도", "F1", "AUC", "접전정확도"]:
        v = res[c]
        print(f"  {c:<8} 평균 {v.mean():.4f} ± {v.std():.4f}  "
              f"(최소 {v.min():.4f} ~ 최대 {v.max():.4f})")
    ok = (res["정확도"] >= 0.70).sum()
    print(f"  → 하한 기준 0.70 이상: {ok}/10회")

    # 승리요인 순위 안정성
    ranks = pd.concat(coef_ranks, axis=1)
    top3 = (ranks <= 3).sum(axis=1).sort_values(ascending=False)
    print("\n[승리요인 안정성] 10회 중 '상위 3위 안'에 든 횟수")
    for f, n in top3[top3 > 0].items():
        print(f"  {f:<28} {int(n):>2}/10회   평균 순위 {ranks.loc[f].mean():.1f}")
    return res


def experiment_b():
    """실험 B — 프로 경기, 10분 vs 15분. 시드마다 분할부터 다시 한다."""
    print("\n" + "=" * 66)
    print("실험 B 반복 — 프로 경기 10,656판, 10분 vs 15분, 시드 10개")
    print("=" * 66)
    raw = pd.read_csv("data/oracles_elixir_2022_match_data.csv", low_memory=False)
    blue = raw[(raw["position"] == "team") & (raw["side"] == "Blue")]
    need = [f"{c}at{t}" for t in (10, 15)
            for c in ("golddiff", "xpdiff", "csdiff", "kills", "opp_kills",
                      "assists", "opp_assists")]
    df = blue.dropna(subset=need).copy()
    y = df["result"].astype(int)
    X10, X15 = build_expb(df, 10), build_expb(df, 15)

    rows = []
    for s in SEEDS:
        i_tr, i_te = train_test_split(df.index, test_size=0.2,
                                      random_state=s, stratify=y)
        out = {"seed": s}
        preds = {}
        for minute, X in [(10, X10), (15, X15)]:
            m = pipe(s).fit(X.loc[i_tr], y.loc[i_tr])
            p = (m.predict_proba(X.loc[i_te])[:, 1] >= 0.5).astype(int)
            preds[minute] = p
            out[f"{minute}분"] = accuracy_score(y.loc[i_te], p)
        out["차이"] = out["15분"] - out["10분"]
        # 10분 접전 경기에서의 개선폭
        close = X10.loc[i_te, "GoldDiff"].abs().values < 1000
        out["접전_10분"] = accuracy_score(y.loc[i_te][close], preds[10][close])
        out["접전_15분"] = accuracy_score(y.loc[i_te][close], preds[15][close])
        out["접전_개선"] = out["접전_15분"] - out["접전_10분"]
        rows.append(out)

    res = pd.DataFrame(rows).set_index("seed")
    print(res.round(4).to_string())
    print("\n[요약] 10회 반복 결과")
    for c in ["10분", "15분", "차이", "접전_개선"]:
        v = res[c]
        print(f"  {c:<10} 평균 {v.mean():+.4f} ± {v.std():.4f}  "
              f"(최소 {v.min():+.4f} ~ 최대 {v.max():+.4f})")
    print(f"  → 15분이 10분보다 나은 횟수: {(res['차이'] > 0).sum()}/10회")
    print(f"  → 접전 구간이 개선된 횟수: {(res['접전_개선'] > 0).sum()}/10회")
    return res


if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)
    a = experiment_a()
    b = experiment_b()
    a.round(4).to_csv("reports/repeat_experimentA.csv", encoding="utf-8-sig")
    b.round(4).to_csv("reports/repeat_experimentB.csv", encoding="utf-8-sig")
    print("\n[저장] reports/repeat_experimentA.csv · repeat_experimentB.csv")
