# 실험 B — 10분 vs 15분 시점 비교 (프로젝트 제목의 질문에 답하는 실험)
#
# 실행: 프로젝트 폴더에서  python src/timepoint_compare.py
#
# 질문: "5분을 더 보면 승패를 얼마나 더 잘 알 수 있는가? 승리 양상은 어떻게 바뀌는가?"
#
# ★ 이 실험의 핵심은 '통제'다. 시점 하나만 바꾸고 나머지는 전부 고정한다.
#   - 같은 경기 집합 (10분·15분 기록이 둘 다 있는 경기만)
#   - 같은 피처 정의 (두 시점에서 똑같이 계산되는 5개만)
#   - 같은 분할·같은 전처리·같은 모델·같은 시드
#   그래야 성능 차이를 "시점 때문"이라고 말할 수 있다.
#
# ⚠️ 실험 A(Kaggle 다이아 랭크)와 절대 수치를 비교하면 안 된다.
#    데이터·실력대(프로)·피처 수가 모두 다르다. 여기서는 10분과 15분끼리만 비교한다.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)

import time

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42
CSV = "data/oracles_elixir_2022_match_data.csv"

# 두 시점에서 똑같이 계산되는 피처만 쓴다 (통제의 핵심)
# dragons·heralds·towers·firstblood 는 경기 전체 누적값이라 "10분 시점 값"이 없다.
# 넣으면 미래 정보 누수이므로 제외했다.
FEATURES = ["GoldDiff", "ExpDiff", "CSDiff", "KillsDiff", "AssistsDiff"]


def build(df: pd.DataFrame, minute: int) -> pd.DataFrame:
    """지정한 시점(10 또는 15)의 피처 5개를 만든다. 계산식은 두 시점이 동일하다."""
    t = minute
    out = pd.DataFrame(index=df.index)
    out["GoldDiff"] = df[f"golddiffat{t}"]
    out["ExpDiff"] = df[f"xpdiffat{t}"]
    out["CSDiff"] = df[f"csdiffat{t}"]
    out["KillsDiff"] = df[f"killsat{t}"] - df[f"opp_killsat{t}"]
    out["AssistsDiff"] = df[f"assistsat{t}"] - df[f"opp_assistsat{t}"]
    return out[FEATURES]


def main():
    os.makedirs("reports", exist_ok=True)
    print("=" * 64)
    print("실험 B — 10분 vs 15분 시점 비교 (Oracle's Elixir 2022 프로 경기)")
    print("=" * 64)

    # ---------- 1. 표본 통제 ----------
    raw = pd.read_csv(CSV, low_memory=False)
    team = raw[raw["position"] == "team"]
    # ★ 한 경기 = 2행(블루·레드)이다. 그대로 쓰면 같은 경기가 학습·시험 양쪽에 들어가
    #   중복 누수가 난다. 블루 행만 남겨 "경기 1판 = 1행"으로 만든다.
    #   (golddiffat10 은 이미 '내 팀 − 상대 팀' 이므로 블루 기준 차이가 된다)
    blue = team[team["side"] == "Blue"]
    need = [f"{c}at{t}" for t in (10, 15)
            for c in ("golddiff", "xpdiff", "csdiff", "kills", "opp_kills",
                      "assists", "opp_assists")]
    df = blue.dropna(subset=need).copy()
    print(f"\n[표본 통제] 전체 {len(raw):,}행 → 팀 행 {len(team):,} → 블루 행 {len(blue):,}")
    print(f"            → 10·15분 기록이 둘 다 있는 경기 {len(df):,}판만 사용")
    print(f"            리그 {df['league'].nunique()}개 · 블루 승률 {df['result'].mean():.3f}")

    y = df["result"].astype(int)
    X10, X15 = build(df, 10), build(df, 15)

    # ---------- 2. 같은 분할 (시점마다 다르면 비교가 성립하지 않는다) ----------
    idx_tr, idx_te = train_test_split(
        df.index, test_size=0.2, random_state=SEED, stratify=y)
    print(f"[분할] 학습 {len(idx_tr):,} / 시험 {len(idx_te):,} — 두 시점이 같은 분할을 쓴다")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    results, coef_table = {}, {}

    for minute, X in [(10, X10), (15, X15)]:
        pipe = Pipeline([("scaler", StandardScaler()),
                         ("model", LogisticRegression(max_iter=1000, random_state=SEED))])
        t0 = time.time()
        res = cross_validate(pipe, X.loc[idx_tr], y.loc[idx_tr], cv=cv,
                             scoring=["accuracy"], return_train_score=True, n_jobs=1)
        pipe.fit(X.loc[idx_tr], y.loc[idx_tr])
        proba = pipe.predict_proba(X.loc[idx_te])[:, 1]
        pred = (proba >= 0.5).astype(int)
        results[minute] = {
            "cv": res["test_accuracy"].mean(), "std": res["test_accuracy"].std(),
            "holdout": accuracy_score(y.loc[idx_te], pred),
            "auc": roc_auc_score(y.loc[idx_te], proba),
            "proba": proba, "pred": pred, "sec": time.time() - t0,
        }
        coef_table[f"{minute}분"] = pd.Series(
            pipe.named_steps["model"].coef_[0], index=FEATURES).round(3)

    # ---------- 3. 성능 비교 ----------
    r10, r15 = results[10], results[15]
    base = max(y.loc[idx_te].mean(), 1 - y.loc[idx_te].mean())
    print("\n" + "-" * 64)
    print("[결과 1] 5분을 더 보면 얼마나 더 맞히나")
    print("-" * 64)
    print(f"{'시점':<8}{'교차검증':>16}{'홀드아웃':>12}{'AUC':>10}")
    for m, r in results.items():
        print(f"{m}분{'':<5}{r['cv']:>10.4f} ±{r['std']:.4f}{r['holdout']:>12.4f}{r['auc']:>10.4f}")
    print(f"찍기{'':<5}{base:>10.4f}")
    d_cv = r15["cv"] - r10["cv"]
    d_ho = r15["holdout"] - r10["holdout"]
    print(f"\n→ 5분 추가 효과: 교차검증 {d_cv:+.4f} ({d_cv*100:+.2f}%p) · "
          f"홀드아웃 {d_ho:+.4f} ({d_ho*100:+.2f}%p) · AUC {r15['auc']-r10['auc']:+.4f}")

    # ---------- 4. 승리 양상 변화: 무엇이 중요해지는가 ----------
    print("\n" + "-" * 64)
    print("[결과 2] 승리 양상 변화 — 표준화 계수 (클수록 승패에 크게 작용)")
    print("-" * 64)
    coefs = pd.DataFrame(coef_table)
    coefs["변화"] = (coefs["15분"] - coefs["10분"]).round(3)
    print(coefs.to_string())
    coefs.to_csv("reports/expB_coef_shift.csv", encoding="utf-8-sig")

    # ---------- 5. 격차가 얼마나 벌어지는가 ----------
    print("\n" + "-" * 64)
    print("[결과 3] 격차 자체의 변화 — 10분 → 15분")
    print("-" * 64)
    for f in ["GoldDiff", "ExpDiff", "KillsDiff"]:
        a, b = X10[f].abs().mean(), X15[f].abs().mean()
        print(f"  |{f}| 평균: {a:>8.1f} → {b:>8.1f}  ({b/a:.2f}배)")
    close10 = (X10["GoldDiff"].abs() < 1000).mean()
    close15 = (X15["GoldDiff"].abs() < 1000).mean()
    print(f"  골드차 1,000 미만(접전) 비율: {close10:.1%} → {close15:.1%}")

    # ---------- 6. 핵심: 10분 접전 경기는 15분에 풀리는가 ----------
    print("\n" + "-" * 64)
    print("[결과 4] ★ 10분에 접전이던 경기, 5분 뒤엔 예측할 수 있게 되나")
    print("-" * 64)
    te = pd.DataFrame({
        "gold10": X10.loc[idx_te, "GoldDiff"].values,
        "gold15": X15.loc[idx_te, "GoldDiff"].values,
        "y": y.loc[idx_te].values,
        "ok10": (r10["pred"] == y.loc[idx_te].values).astype(int),
        "ok15": (r15["pred"] == y.loc[idx_te].values).astype(int)})
    bins = [0, 1000, 2500, np.inf]
    labels = ["접전(<1k)", "우세(1k~2.5k)", "크게 우세(2.5k+)"]
    te["10분구간"] = pd.cut(te["gold10"].abs(), bins=bins, labels=labels, right=False)
    tab = te.groupby("10분구간", observed=True).agg(
        경기수=("y", "size"), 정확도_10분=("ok10", "mean"), 정확도_15분=("ok15", "mean")).round(4)
    tab["개선"] = (tab["정확도_15분"] - tab["정확도_10분"]).round(4)
    tab["비중_%"] = (tab["경기수"] / tab["경기수"].sum() * 100).round(1)
    print(tab.to_string())
    tab.to_csv("reports/expB_close_games.csv", encoding="utf-8-sig")

    # 접전이 5분 뒤 어디로 갔나
    close = te[te["gold10"].abs() < 1000]
    still = (close["gold15"].abs() < 1000).mean()
    print(f"\n  10분 접전 경기 {len(close)}판 중 15분에도 접전인 경기: {still:.1%}")
    print(f"  → 나머지 {1-still:.1%}는 5분 사이에 한쪽으로 기울었다")

    # ---------- 7. 그림 ----------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = np.arange(len(tab))
    ax[0].bar(x - 0.2, tab["정확도_10분"], 0.4, label="10분 정보")
    ax[0].bar(x + 0.2, tab["정확도_15분"], 0.4, label="15분 정보")
    ax[0].set_xticks(x); ax[0].set_xticklabels(tab.index, fontsize=9)
    ax[0].axhline(0.5, color="gray", ls=":")
    ax[0].set_title("10분 상황별 예측 정확도 — 5분 추가 효과")
    ax[0].set_ylim(0.4, 1.0); ax[0].legend()

    ax[1].scatter(te["gold10"], te["gold15"], s=4, alpha=0.3,
                  c=te["y"], cmap="coolwarm")
    ax[1].axhline(0, color="gray", lw=0.5); ax[1].axvline(0, color="gray", lw=0.5)
    ax[1].axvspan(-1000, 1000, color="orange", alpha=0.15)
    ax[1].set_xlabel("10분 골드차"); ax[1].set_ylabel("15분 골드차")
    ax[1].set_title("격차의 이동 (주황=10분 접전 구간)")
    fig.tight_layout()
    fig.savefig("reports/expB_timepoint.png", dpi=120)
    print("\n[저장] reports/expB_timepoint.png · expB_coef_shift.csv · expB_close_games.csv")

    # ---------- 8. 기록 ----------
    rows = [{"date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
             "run": f"expB_logreg_{m}min_pro(n={len(df)})",
             "cv_acc_mean": round(results[m]["cv"], 4),
             "cv_acc_std": round(results[m]["std"], 4),
             "cv_f1_mean": "", "cv_f1_std": "", "train_acc_mean": "",
             "train_f1_mean": "", "sec": round(results[m]["sec"], 2)} for m in (10, 15)]
    from runlog import COLUMNS
    pd.DataFrame(rows)[COLUMNS].to_csv("runs.csv", mode="a", index=False, header=False)
    print("[기록] runs.csv 에 두 시점 결과 추가")


if __name__ == "__main__":
    main()
