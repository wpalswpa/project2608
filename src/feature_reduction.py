# 페이즈 2 — 상관이 높은 피처를 덜어내면 무엇이 달라지나
#
# 실행: 프로젝트 폴더에서  python src/feature_reduction.py
#
# 왜 하나
#   diff13 에는 서로 강하게 얽힌 지표가 있다 (킬↔골드 +0.92, 경험치↔레벨 +0.92).
#   이러면 골드 같은 대표 지표가 가중치를 거의 다 가져가고, 나머지는 남은 몫이 없어
#   계수가 0 근처거나 부호가 뒤집힌다. 점수는 멀쩡한데 "무엇이 승패를 가르나"의 답이 왜곡된다.
#
#   그래서 상관행렬을 눈으로 확인하고, 겹치는 지표를 덜어낸 구성을 만들어
#   ① 점수가 유지되는가 ② 요인 순위가 안정되는가 를 비교한다.
#
# 순서 (시점 비교 전에 수행)
#   1. 상관행렬 히트맵 — 어떤 지표들이 한 덩어리인지 본다
#   2. VIF — 다중공선성을 수치로 확인
#   3. 상관 임계값별로 지표를 덜어낸 구성 4가지를 만들어 성능·해석을 비교
#   4. 시드 10개 반복으로 "요인 순위가 흔들리지 않는가"를 확인
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()

import itertools
import time

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from finalize_model import DIFF13, build_diff13_from_csv, load_data

SEED = 42
SEEDS = [42, 0, 1, 7, 13, 21, 77, 100, 202, 777]


def pipe(seed=SEED):
    return Pipeline([("scaler", StandardScaler()),
                     ("model", LogisticRegression(max_iter=1000, random_state=seed))])


def vif(X: pd.DataFrame) -> pd.Series:
    """분산팽창계수 — 그 지표를 나머지로 예측했을 때 얼마나 잘 맞는가.
    10 이상이면 다른 지표들로 거의 설명되는, 즉 중복에 가까운 지표다."""
    from sklearn.linear_model import LinearRegression
    out = {}
    Z = (X - X.mean()) / X.std()
    for c in X.columns:
        r2 = LinearRegression().fit(Z.drop(columns=[c]), Z[c]).score(Z.drop(columns=[c]), Z[c])
        out[c] = np.inf if r2 >= 1 - 1e-12 else 1 / (1 - r2)
    return pd.Series(out).sort_values(ascending=False)


def drop_correlated(X: pd.DataFrame, y: pd.Series, threshold: float) -> list:
    """상관이 threshold 이상인 쌍에서, 정답과 덜 관련된 쪽을 버린다.
    (둘 중 하나만 남기면 되므로 정답을 더 잘 설명하는 쪽을 남긴다)"""
    corr = X.corr().abs()
    target = X.corrwith(y).abs()
    dropped = set()
    for a, b in itertools.combinations(X.columns, 2):
        if a in dropped or b in dropped:
            continue
        if corr.loc[a, b] >= threshold:
            dropped.add(a if target[a] < target[b] else b)
    return [c for c in X.columns if c not in dropped]


def evaluate(X_tr, y_tr, X_te, y_te, cols, name):
    """한 구성에 대해 성능과 해석 안정성을 함께 잰다."""
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    scores = cross_val_score(pipe(), X_tr[cols], y_tr, cv=cv, scoring="accuracy", n_jobs=1)
    m = pipe().fit(X_tr[cols], y_tr)
    acc = accuracy_score(y_te, m.predict(X_te[cols]))
    coef = pd.Series(m.named_steps["model"].coef_[0], index=cols)

    # 해석 안정성: 시드를 바꿔가며 1위 요인이 유지되는가 · 부호가 뒤집히는 지표가 몇 개인가
    tops, flips = [], []
    for s in SEEDS:
        Xa, Xb, ya, yb = train_test_split(pd.concat([X_tr[cols], X_te[cols]]),
                                          pd.concat([y_tr, y_te]),
                                          test_size=0.2, random_state=s,
                                          stratify=pd.concat([y_tr, y_te]))
        c = pd.Series(pipe(s).fit(Xa, ya).named_steps["model"].coef_[0], index=cols)
        tops.append(c.abs().idxmax())
        # 정답과 양의 상관인데 계수가 음수인 지표 = 해석이 뒤집힌 것
        tgt = pd.concat([X_tr[cols], X_te[cols]]).corrwith(pd.concat([y_tr, y_te]))
        flips.append(int(((tgt > 0.1) & (c < 0)).sum()))

    return {
        "구성": name, "지표수": len(cols),
        "교차검증": scores.mean(), "표준편차": scores.std(), "홀드아웃": acc,
        "1위요인": coef.abs().idxmax(),
        "1위유지": f"{tops.count(max(set(tops), key=tops.count))}/10",
        "부호뒤집힘": float(np.mean(flips)),
        "cols": cols,
    }


def main():
    os.makedirs("reports", exist_ok=True)
    X_tr, y_tr, X_te, y_te, source = load_data()
    print("=" * 70)
    print("페이즈 2 — 상관이 높은 피처를 덜어내면 무엇이 달라지나")
    print("=" * 70)
    print(f"[데이터] {source} · 학습 {len(y_tr):,} / 시험 {len(y_te):,}\n")

    # ── 1. 상관행렬 히트맵 ────────────────────────────────────
    corr = X_tr.corr()
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    ax = axes[0]
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=90, fontsize=8)
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.columns, fontsize=8)
    for i in range(len(corr)):
        for j in range(len(corr)):
            v = corr.iloc[i, j]
            if i != j and abs(v) >= 0.4:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if abs(v) > 0.7 else "black")
    fig.colorbar(im, ax=ax, shrink=0.8, label="상관계수")
    ax.set_title("지표끼리의 상관 — 0.4 이상만 숫자 표시", pad=12)

    # 정답과의 상관 vs 모델 계수 (해석이 뒤집히는 지표를 보여준다)
    base = pipe().fit(X_tr, y_tr)
    coef0 = pd.Series(base.named_steps["model"].coef_[0], index=DIFF13)
    tgt0 = X_tr.corrwith(y_tr)
    ax = axes[1]
    flip = (tgt0 > 0.1) & (coef0 < 0)
    ax.scatter(tgt0[~flip], coef0[~flip], s=60, color="#2f6fe4", label="정상")
    ax.scatter(tgt0[flip], coef0[flip], s=90, color="#c0392b", label="부호 뒤집힘")
    for c in DIFF13:
        ax.annotate(c, (tgt0[c], coef0[c]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="gray", lw=0.8); ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("정답과의 상관 (단독으로 보면 얼마나 관련 있나)")
    ax.set_ylabel("모델이 준 가중치 (다른 지표를 고려한 뒤)")
    ax.set_title("오른쪽 아래 빨간 점 = 관련 있는데 가중치가 음수\n(대표 지표가 몫을 가져간 결과)", pad=12)
    ax.legend()
    fig.tight_layout()
    fig.savefig("reports/figures/phase2_correlation.png", dpi=130, bbox_inches="tight")

    print("[1] 상관 0.7 이상인 쌍")
    pairs = [(a, b, corr.loc[a, b]) for a, b in itertools.combinations(DIFF13, 2)
             if abs(corr.loc[a, b]) >= 0.7]
    for a, b, v in sorted(pairs, key=lambda x: -abs(x[2])):
        print(f"    {a:30} ↔ {b:28} {v:+.3f}")
    print(f"\n    정답과 양의 상관인데 가중치는 음수인 지표: {list(coef0[flip].index)}")
    print("    → 대표 지표(골드)가 몫을 가져가 해석이 뒤집힌 것")

    # ── 2. VIF ────────────────────────────────────────────────
    v = vif(X_tr)
    print("\n[2] VIF (10 이상이면 다른 지표로 거의 설명되는 중복 지표)")
    for name, val in v.head(6).items():
        mark = "  ← 중복 의심" if val >= 10 else ""
        print(f"    {name:30} {val:7.2f}{mark}")

    # ── 3. 구성별 비교 ────────────────────────────────────────
    print("\n[3] 상관이 높은 지표를 덜어낸 구성 비교")
    configs = [("전체 13개 (현재)", DIFF13)]
    for th in (0.9, 0.8, 0.7):
        cols = drop_correlated(X_tr, y_tr, th)
        configs.append((f"상관 {th} 이상 제거 ({len(cols)}개)", cols))
    configs.append(("골드+경험치 2개", ["GoldDiff", "ExpDiff"]))

    rows = []
    for name, cols in configs:
        t0 = time.time()
        r = evaluate(X_tr, y_tr, X_te, y_te, cols, name)
        r["초"] = round(time.time() - t0, 1)
        rows.append(r)
        print(f"    {name:24} 지표 {r['지표수']:2}개 · CV {r['교차검증']:.4f}±{r['표준편차']:.4f}"
              f" · 홀드아웃 {r['홀드아웃']:.4f} · 1위 {r['1위요인']:12} ({r['1위유지']})"
              f" · 뒤집힘 {r['부호뒤집힘']:.1f}개")

    res = pd.DataFrame(rows).drop(columns=["cols"])
    res.to_csv("reports/tables/phase2_feature_sets.csv", index=False, encoding="utf-8-sig")

    # 제거된 지표 기록
    with open("reports/tables/phase2_dropped.txt", "w", encoding="utf-8") as f:
        for (name, cols), r in zip(configs, rows):
            dropped = [c for c in DIFF13 if c not in cols]
            f.write(f"{name}\n  남김: {cols}\n  제거: {dropped}\n\n")

    # ── 4. 그림 ───────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(len(res))
    ax = axes[0]
    ax.bar(x - 0.2, res["교차검증"], 0.4, label="교차검증", color="#8fa8c8")
    ax.bar(x + 0.2, res["홀드아웃"], 0.4, label="홀드아웃", color="#2f6fe4")
    for i, (a, b) in enumerate(zip(res["교차검증"], res["홀드아웃"])):
        ax.text(i - 0.2, a + 0.004, f"{a:.3f}", ha="center", fontsize=8)
        ax.text(i + 0.2, b + 0.004, f"{b:.3f}", ha="center", fontsize=8)
    ax.axhline(0.5010, color="gray", ls=":", lw=1.2, label="찍기 0.501")
    ax.set_xticks(x); ax.set_xticklabels(res["구성"], fontsize=8, rotation=12)
    ax.set_ylim(0.48, 0.79); ax.set_ylabel("정확도")
    ax.set_title("지표를 덜어내도 점수는 유지되는가", pad=10); ax.legend(fontsize=8.5)

    ax = axes[1]
    ax.bar(x, res["부호뒤집힘"], color="#c0392b", width=0.5)
    for i, v2 in enumerate(res["부호뒤집힘"]):
        ax.text(i, v2 + 0.06, f"{v2:.1f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(res["구성"], fontsize=8, rotation=12)
    ax.set_ylabel("부호가 뒤집힌 지표 수 (시드 10회 평균)")
    ax.set_title("덜어낼수록 해석이 깨끗해지는가\n(적을수록 좋다)", pad=10)
    fig.tight_layout()
    fig.savefig("reports/figures/phase2_comparison.png", dpi=130, bbox_inches="tight")

    print("\n[저장] reports/figures/phase2_correlation.png · phase2_comparison.png")
    print("       reports/tables/phase2_feature_sets.csv · phase2_dropped.txt")

    # ── 5. 결론 ───────────────────────────────────────────────
    best_acc = res.loc[res["홀드아웃"].idxmax()]
    clean = res.loc[res["부호뒤집힘"].idxmin()]
    print("\n" + "=" * 70)
    print(f"점수가 가장 높은 구성 : {best_acc['구성']} ({best_acc['홀드아웃']:.4f})")
    print(f"해석이 가장 깨끗한 구성: {clean['구성']} (뒤집힘 {clean['부호뒤집힘']:.1f}개)")
    print("=" * 70)


if __name__ == "__main__":
    main()
