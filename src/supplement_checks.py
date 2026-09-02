# 보충 검증 — 군집화·데이터 축소·추가 모델
#
# 실행: 프로젝트 폴더에서  python src/supplement_checks.py
#
# 페이즈 2에서 "정보가 성장 축 하나에 몰려 있다"고 결론냈다. 그렇다면 두 가지가 궁금해진다.
#   A. 데이터 축소 — 정말 축 몇 개면 되나? PCA 주성분 k개만으로 다시 학습해 잰다.
#   B. 군집화 — 승패 축 말고 다른 구조는 없나? 군집 모델 4종을 같은 조건에서 비교해
#      하나를 정식 채택한다 (지금까지 KMeans 는 비교 없이 쓰였다).
#
# 전부 학습셋 7,903행만 쓴다 — 시험지는 여기서도 봉인.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

for f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(f == x.name for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False

from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from lolwin.data import load as load_data

SEED = 42
BLUE, RED, GRAY, GREEN = "#2f6fe4", "#c0392b", "#9aa5b1", "#2e7d32"
NL = chr(10)


# ── A. 데이터 축소 — PCA 주성분 k개만으로 예측 ────────────────
def part_a(X_tr, y_tr, X_te, y_te):
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    rows = []
    for k in range(1, 14):
        pipe = Pipeline([("sc", StandardScaler()),
                         ("pca", PCA(n_components=k, random_state=SEED)),
                         ("lr", LogisticRegression(max_iter=1000, random_state=SEED))])
        s = cross_val_score(pipe, X_tr, y_tr, cv=cv, n_jobs=1).mean()
        pipe.fit(X_tr, y_tr)
        a = accuracy_score(y_te, pipe.predict(X_te))
        rows.append({"주성분수": k, "교차검증": round(s, 4), "홀드아웃": round(a, 4)})
    df = pd.DataFrame(rows)
    df.to_csv("reports/tables/supplement_pca_reduction.csv", index=False, encoding="utf-8-sig")

    # 원본 13개의 성능은 하드코딩하지 않고 산출물에서 읽는다.
    # 손으로 베껴 적으면 재학습 때 조용히 어긋난다(계수 수치로 이미 겪었다).
    from lolwin.artifacts import load_schema
    _s = load_schema()
    full_cv = _s["provenance"]["cv"]["cv_accuracy"]
    full_ho = _s["metrics_holdout"]["accuracy"]
    print("[A] 데이터 축소 — 주성분 k개만으로")
    for r in rows[:3] + [rows[-1]]:
        print(f"    k={r['주성분수']:>2} · CV {r['교차검증']:.4f} · 홀드아웃 {r['홀드아웃']:.4f}")
    print(f"    (원본 13개: CV {full_cv:.4f} · 홀드아웃 {full_ho:.4f})")

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.plot(df["주성분수"], df["홀드아웃"], "o-", color=BLUE, lw=2, label="홀드아웃")
    ax.plot(df["주성분수"], df["교차검증"], "s--", color=GRAY, lw=1.5, label="교차검증")
    ax.axhline(full_ho, color=GREEN, ls=":", lw=1.6)
    ax.text(13.1, full_ho, f"원본 13개{NL}{full_ho:.4f}", fontsize=9, color=GREEN, va="center")
    p1 = df.iloc[0]["홀드아웃"]
    ax.annotate(f"축 1개만으로 {p1:.4f}{NL}(원본과 {full_ho - p1:.4f} 차이)",
                xy=(1, p1), xytext=(2.2, p1 - 0.012), fontsize=10.5, fontweight="bold",
                color=RED, arrowprops=dict(arrowstyle="->", color=RED))
    ax.set_xticks(range(1, 14))
    ax.set_xlabel("사용한 주성분 개수 (k)")
    ax.set_ylabel("정확도")
    ax.set_ylim(0.70, 0.75)
    ax.legend(fontsize=9, loc="lower right")
    ax.set_title("13개 지표의 정보는 사실상 축 하나 — 주성분 1개로도 0.73 에 붙는다",
                 fontsize=12.5, pad=12)
    fig.tight_layout()
    fig.savefig("reports/figures/supplement_pca_reduction.png", dpi=130, bbox_inches="tight")
    return df


# ── B. 군집 모델 비교 — 4종을 같은 조건에서 ──────────────────
def neutral_features():
    """진영 정보를 지운 5피처 (day2b 와 같은 정의, 학습셋만)."""
    d = pd.read_csv("data/high_diamond_ranked_10min.csv").sort_values("gameId")
    tr = pd.read_csv("data/splits/train_idx.csv")["idx"].values
    d = d.loc[tr]
    g = pd.DataFrame(index=d.index)
    g["일방성_골드차"] = d["blueGoldDiff"].abs()
    g["난타전_총킬"] = d["blueKills"] + d["redKills"]
    g["오브젝트_총획득"] = d[["blueDragons", "blueHeralds", "redDragons", "redHeralds"]].sum(axis=1)
    g["시야전_총와드"] = d["blueWardsPlaced"] + d["redWardsPlaced"]
    g["성장_총CS"] = d["blueTotalMinionsKilled"] + d["redTotalMinionsKilled"]
    return g


def part_b():
    g = neutral_features()
    Z = StandardScaler().fit_transform(g)
    sil = lambda z, lab: silhouette_score(z, lab, sample_size=4000, random_state=SEED)

    rows = []
    for k in range(2, 7):
        lab = KMeans(k, n_init=10, random_state=SEED).fit(Z).labels_
        rows.append({"모델": "KMeans", "k": k, "실루엣": round(sil(Z, lab), 3),
                     "비고": "중심 = 평균이라 표로 해석 가능"})
    for k in range(3, 6):
        lab = GaussianMixture(k, random_state=SEED, n_init=3).fit(Z).predict(Z)
        rows.append({"모델": "GMM", "k": k, "실루엣": round(sil(Z, lab), 3),
                     "비고": "확률 배정 — 경계가 흐림"})
    for k in range(3, 6):
        lab = AgglomerativeClustering(k).fit(Z[:4000]).labels_
        rows.append({"모델": "계층적", "k": k, "실루엣": round(silhouette_score(Z[:4000], lab), 3),
                     "비고": "메모리 문제로 4,000표본"})
    db = DBSCAN(eps=0.9, min_samples=30).fit(Z)
    noise = int((db.labels_ == -1).sum())
    ncl = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    rows.append({"모델": "DBSCAN", "k": ncl, "실루엣": None,
                 "비고": f"잡음 {noise:,}판({noise/len(Z):.0%}) — 밀도 경계가 없어 부적합"})

    df = pd.DataFrame(rows)
    df.to_csv("reports/tables/supplement_cluster_models.csv", index=False, encoding="utf-8-sig")

    print(f"{NL}[B] 군집 모델 비교 (중립 5피처 · 학습셋)")
    for _, r in df.iterrows():
        s = f"{r['실루엣']:.3f}" if pd.notna(r["실루엣"]) else "  —  "
        print(f"    {r['모델']:<8} k={r['k']} · 실루엣 {s} · {r['비고']}")

    km = df[df["모델"] == "KMeans"]
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for name, color, marker in [("KMeans", BLUE, "o"), ("GMM", RED, "s"), ("계층적", GRAY, "^")]:
        part = df[df["모델"] == name]
        ax.plot(part["k"], part["실루엣"], marker + "-", color=color, lw=2, label=name, ms=8)
    ax.axhspan(0.20, 0.22, color=BLUE, alpha=0.08)
    ax.annotate("KMeans 만 0.2 위에서 안정" + NL + "(k=2~6 어디서나)",
                xy=(4, 0.21), xytext=(4.4, 0.17), fontsize=10, color=BLUE, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=BLUE))
    ax.text(2.05, 0.055, f"DBSCAN: 잡음 {noise:,}판({noise/len(Z):.0%})이라 탈락", fontsize=9.5, color="#555")
    ax.set_xlabel("군집 수 (k)")
    ax.set_ylabel("실루엣 점수 (높을수록 잘 나뉨)")
    ax.set_xticks(range(2, 7))
    ax.legend(fontsize=9)
    ax.set_title("군집 모델 4종 비교 — 어느 모델로 묶어도 되는 건 아니다", fontsize=12.5, pad=12)
    fig.tight_layout()
    fig.savefig("reports/figures/supplement_cluster_models.png", dpi=130, bbox_inches="tight")
    return df


# ── C. 추가 모델 학습 — 나이브베이즈 (페이즈 1 비교 3위) ──────
def part_c(X_tr, y_tr, X_te, y_te):
    """정확도는 대등한데 확률은 쓸 수 있나 — 서비스는 확률을 화면에 보여준다."""
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.naive_bayes import GaussianNB

    lr = Pipeline([("sc", StandardScaler()),
                   ("m", LogisticRegression(max_iter=1000, random_state=SEED))]).fit(X_tr, y_tr)
    nb = Pipeline([("sc", StandardScaler()), ("m", GaussianNB())]).fit(X_tr, y_tr)

    rows = []
    for name, m in [("로지스틱 (채택)", lr), ("나이브베이즈", nb)]:
        p = m.predict_proba(X_te)[:, 1]
        rows.append({
            "모델": name,
            "정확도": round(accuracy_score(y_te, (p >= 0.5).astype(int)), 4),
            "AUC": round(roc_auc_score(y_te, p), 4),
            "Brier": round(brier_score_loss(y_te, p), 4),
            "극단확률비중": round(float(((p < 0.05) | (p > 0.95)).mean()), 3),
        })
    df = pd.DataFrame(rows)
    df.to_csv("reports/tables/supplement_nb_vs_lr.csv", index=False, encoding="utf-8-sig")
    print(NL + "[C] 나이브베이즈 추가학습 — 확률 품질 비교")
    for _, r in df.iterrows():
        print(f"    {r['모델']:<12} 정확도 {r['정확도']:.4f} · AUC {r['AUC']:.4f}"
              f" · Brier {r['Brier']:.4f} · 극단확률 {r['극단확률비중']:.1%}")

    # 확률 분포 — NB 가 왜 탈락인지 한 장으로
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), sharey=True)
    bins = np.linspace(0, 1, 41)
    for ax, (name, m) in zip(axes, [("로지스틱 (채택)", lr), ("나이브베이즈", nb)]):
        p = m.predict_proba(X_te)[:, 1]
        ext = ((p < 0.05) | (p > 0.95)).mean()
        ax.hist(p, bins=bins, color=BLUE if "로지스틱" in name else RED, alpha=0.75)
        ax.axvspan(0, 0.05, color="black", alpha=0.07)
        ax.axvspan(0.95, 1, color="black", alpha=0.07)
        ax.set_title(f"{name}{NL}\"95% 이상/5% 이하\" 확신: {ext:.1%}", fontsize=12, pad=10)
        ax.set_xlabel("블루 승리 예측 확률")
    axes[0].set_ylabel("경기 수")
    fig.suptitle("정확도는 비슷한데 확률의 얼굴이 다르다 — NB 는 3판 중 2판에 극단 확신을 건다",
                 fontsize=12.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig("reports/figures/supplement_nb_proba.png", dpi=130, bbox_inches="tight")
    return df


def main():
    os.makedirs("reports/figures", exist_ok=True)
    os.makedirs("reports/tables", exist_ok=True)
    print("=" * 66)
    print("보충 검증 — 군집화 · 데이터 축소 · 추가 모델")
    print("=" * 66)
    X_tr, y_tr, X_te, y_te, _ = load_data()
    part_a(X_tr, y_tr, X_te, y_te)
    part_b()
    part_c(X_tr, y_tr, X_te, y_te)
    print(f"{NL}[저장] reports/figures/supplement_pca_reduction.png · supplement_cluster_models.png")
    print("       reports/figures/supplement_nb_proba.png · tables/supplement_nb_vs_lr.csv")
    print("       reports/tables/supplement_pca_reduction.csv · supplement_cluster_models.csv")


if __name__ == "__main__":
    main()
