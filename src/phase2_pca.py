# 페이즈 2 보충 — "PCA가 안 통한 게 골드 탓이었나?"
#
# 실행: 프로젝트 폴더에서  python src/phase2_pca.py
#
# 배경: 페이즈 1에서 PCA + KMeans(k=2)를 돌렸더니 군집이 그냥 "블루 우세 / 레드 우세"로
#       갈렸다. 골드가 워낙 세서 그런 것 아니냐는 의심이 자연스럽다.
#       그렇다면 골드를 빼고 같은 절차를 돌리면 다른 구조가 나와야 한다. 확인해 본다.
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

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from finalize_model import DIFF13, load_data

SEED = 42
BLUE, RED, GRAY = "#2f6fe4", "#c0392b", "#9aa5b1"
NL = chr(10)


def run(X, y, cols, tag):
    Z = StandardScaler().fit_transform(X[cols])
    p = PCA().fit(Z)
    T = p.transform(Z)
    km = KMeans(2, n_init=10, random_state=SEED).fit(T[:, :2])
    agree = max((km.labels_ == y.values).mean(), (km.labels_ != y.values).mean())
    return {
        "tag": tag, "cols": cols, "ev": p.explained_variance_ratio_,
        "pc1": pd.Series(p.components_[0], index=cols),
        "T": T, "labels": km.labels_, "agree": agree,
    }


def main():
    os.makedirs("reports/figures", exist_ok=True)
    os.makedirs("reports/tables", exist_ok=True)

    X_tr, y_tr, X_te, y_te, src = load_data()
    X, y = X_tr[DIFF13], y_tr
    nogold = [c for c in DIFF13 if c != "GoldDiff"]

    a = run(X, y, DIFF13, "골드 포함 (13개)")
    b = run(X, y, nogold, "골드 제외 (12개)")

    print("=" * 68)
    print("페이즈 2 보충 — PCA 가 안 통한 게 골드 탓이었나")
    print("=" * 68)
    for r in (a, b):
        top = r["pc1"].abs().sort_values(ascending=False).head(4)
        print(f"{NL}[{r['tag']}]")
        print(f"  PC1 설명력 {r['ev'][0]:.1%} · PC2 {r['ev'][1]:.1%}")
        print(f"  PC1 을 만드는 지표: " + " · ".join(f"{k} {r['pc1'][k]:+.2f}" for k in top.index))
        print(f"  군집이 승패와 일치: {r['agree']:.1%}")
    print(f"{NL}→ 골드를 빼도 일치율 {a['agree']:.1%} → {b['agree']:.1%} 로 거의 그대로."
          f"{NL}  PC1 주도 지표만 GoldDiff → ExpDiff 로 바뀌었을 뿐 구조가 같다.")

    # ── 그림 1: PC1 을 무엇이 만드나 ─────────────────────────
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    order = b["pc1"].abs().sort_values(ascending=False).index[::-1]
    yy = np.arange(len(order)); w = 0.38
    ax.barh(yy - w / 2, [abs(a["pc1"].get(k, 0)) for k in order], w,
            label=f"골드 포함 (PC1 {a['ev'][0]:.1%})", color=GRAY)
    ax.barh(yy + w / 2, [abs(b["pc1"].get(k, 0)) for k in order], w,
            label=f"골드 제외 (PC1 {b['ev'][0]:.1%})", color=BLUE)
    ax.set_yticks(yy); ax.set_yticklabels(order, fontsize=9)
    ax.set_xlabel("PC1 에 실린 무게 (절대값)")
    ax.legend(fontsize=9, loc="lower right")
    ax.set_title("골드를 빼도 PC1 은 같은 '성장 축' 이다" + NL +
                 "1등만 GoldDiff → ExpDiff 로 바뀌고 구성원은 그대로", fontsize=13, pad=12)
    fig.tight_layout()
    fig.savefig("reports/figures/phase2_pca_loadings.png", dpi=130, bbox_inches="tight")

    # ── 그림 2: 군집이 여전히 승패를 되비추나 ────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    for ax, r in zip(axes, (a, b)):
        ax.scatter(r["T"][:, 0], r["T"][:, 1], s=4, alpha=0.28,
                   c=[BLUE if v else RED for v in y.values])
        ax.axvline(0, color="black", lw=0.8, ls="--")
        ax.set_xlabel("PC1"); ax.set_ylabel("PC2")
        ax.set_title(f"{r['tag']}" + NL +
                     f"군집이 승패와 일치 {r['agree']:.1%}", fontsize=12, pad=10)
    axes[0].scatter([], [], c=BLUE, label="실제 블루 승", s=22)
    axes[0].scatter([], [], c=RED, label="실제 레드 승", s=22)
    axes[0].legend(fontsize=9, loc="upper left")
    fig.suptitle("골드를 빼도 왼쪽·오른쪽이 그대로 갈린다 — 군집이 여전히 '누가 앞서나'를 되비춘다",
                 fontsize=13.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig("reports/figures/phase2_pca_cluster.png", dpi=130, bbox_inches="tight")

    pd.DataFrame([{
        "구성": r["tag"], "지표수": len(r["cols"]),
        "PC1_설명력": round(float(r["ev"][0]), 4),
        "PC2_설명력": round(float(r["ev"][1]), 4),
        "PC1_1위": r["pc1"].abs().idxmax(),
        "군집_승패_일치": round(float(r["agree"]), 4),
    } for r in (a, b)]).to_csv("reports/tables/phase2_pca.csv", index=False, encoding="utf-8-sig")

    print(f"{NL}[저장] reports/figures/phase2_pca_loadings.png · phase2_pca_cluster.png"
          f"{NL}       reports/tables/phase2_pca.csv")


if __name__ == "__main__":
    main()
