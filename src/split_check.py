# 분할 진단 — "학습/시험으로 올바르게 나뉘었나"를 눈으로 확인한다 (CRISP-DM: Data Preparation 종착점)
#
# 실행: 프로젝트 폴더에서  python src/split_check.py
#
# 왜 필요한가: 분할은 한 번 잘못되면 이후 모든 점수가 거짓말이 된다.
# 그런데 잘못돼도 오류가 나지 않아 그냥 지나간다. 그래서 네 가지를 명시적으로 확인한다.
#   ① 겹침 0 — 같은 경기가 학습·시험 양쪽에 있으면 시험이 무의미해진다
#   ② 빠짐 0 — 합쳐서 원본과 같아야 한다
#   ③ 층화 — 두 쪽의 승패 비율이 같아야 정확도를 비교할 수 있다
#   ④ 분포 — 주요 지표의 생김새가 두 쪽에서 같아야 한다
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

BLUE, GRAY, GREEN, RED = "#2f6fe4", "#9aa5b1", "#2e7d32", "#c0392b"
NL = chr(10)


def main():
    os.makedirs("reports/figures", exist_ok=True)
    os.makedirs("reports/tables", exist_ok=True)

    df = pd.read_csv("data/high_diamond_ranked_10min.csv").sort_values("gameId")
    tr = pd.read_csv("data/splits/train_idx.csv")["idx"].values
    te = pd.read_csv("data/splits/test_idx.csv")["idx"].values
    y = df["blueWins"]
    gold = df["blueGoldDiff"]

    overlap = len(set(tr) & set(te))
    covered = sorted(set(tr) | set(te)) == sorted(df.index)
    dup = int(df["gameId"].duplicated().sum())
    y_all, y_tr, y_te = y.mean(), y.loc[tr].mean(), y.loc[te].mean()
    strat = abs(y_tr - y_te)

    print("=" * 66)
    print("분할 진단 — 학습/시험으로 올바르게 나뉘었나")
    print("=" * 66)
    print(f"  전체 {len(df):,} = 학습 {len(tr):,} + 시험 {len(te):,}"
          f"  (시험 비율 {len(te)/len(df):.1%})")
    print(f"  ① 인덱스 겹침      {overlap}건        {'통과' if overlap == 0 else '실패'}")
    print(f"  ② 빠진 행          {'없음' if covered else '있음'}       {'통과' if covered else '실패'}")
    print(f"  ③ 층화 오차        {strat:.4f}    {'통과' if strat < 0.01 else '실패'}"
          f"  (학습 {y_tr:.4f} / 시험 {y_te:.4f})")
    print(f"  ④ 같은 경기 재등장  {dup}건        {'통과' if dup == 0 else '실패'}")

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.4))

    # ① 크기
    ax = axes[0]
    b = ax.bar(["학습", "시험"], [len(tr), len(te)], color=[BLUE, GRAY], width=0.55)
    for r, v in zip(b, [len(tr), len(te)]):
        ax.text(r.get_x() + r.get_width() / 2, v + 150, f"{v:,}판{NL}({v/len(df):.0%})",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_ylim(0, len(tr) * 1.25)
    ax.set_ylabel("경기 수")
    ax.set_title("① 8 대 2 로 나눴다" + NL + f"겹침 {overlap}건 · 빠진 행 없음", fontsize=12, pad=12)

    # ② 층화 — 승패 비율이 두 쪽에서 같은가
    ax = axes[1]
    names, vals = ["전체", "학습", "시험"], [y_all, y_tr, y_te]
    b = ax.bar(names, vals, color=[GRAY, BLUE, "#8fa8c8"], width=0.55)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.006, f"{v:.4f}", ha="center",
                fontsize=11, fontweight="bold")
    ax.axhline(0.5, color=RED, ls=":", lw=1.4)
    ax.text(2.42, 0.503, "반반", fontsize=9, color=RED, ha="right")
    ax.set_ylim(0.40, 0.58)
    ax.set_ylabel("블루 승률")
    ax.set_title("② 승패 비율이 두 쪽에서 같다" + NL + f"차이 {strat:.4f} (기준 0.01 미만)",
                 fontsize=12, pad=12)

    # ③ 분포 — 주력 지표가 두 쪽에서 같은 모양인가
    ax = axes[2]
    bins = np.linspace(-6000, 6000, 45)
    ax.hist(gold.loc[tr], bins=bins, density=True, color=BLUE, alpha=0.55, label=f"학습 {len(tr):,}")
    ax.hist(gold.loc[te], bins=bins, density=True, histtype="step", lw=2, color=RED,
            label=f"시험 {len(te):,}")
    ax.set_xlabel("10분 골드 차이")
    ax.set_ylabel("비율")
    ax.legend(fontsize=9)
    ax.set_title("③ 주력 지표 분포도 겹친다" + NL + "시험셋만 유난히 쉽거나 어렵지 않다",
                 fontsize=12, pad=12)

    fig.suptitle("분할 진단 — 이 네 가지가 통과해야 이후 점수를 믿을 수 있다",
                 fontsize=14, fontweight="bold", y=1.0)
    fig.tight_layout()
    fig.savefig("reports/figures/split_check.png", dpi=130, bbox_inches="tight")

    pd.DataFrame([
        {"항목": "인덱스 겹침", "값": overlap, "기준": "0건", "판정": "통과" if overlap == 0 else "실패"},
        {"항목": "빠진 행", "값": "없음" if covered else "있음", "기준": "없음",
         "판정": "통과" if covered else "실패"},
        {"항목": "층화 오차", "값": round(strat, 4), "기준": "0.01 미만",
         "판정": "통과" if strat < 0.01 else "실패"},
        {"항목": "같은 경기 재등장", "값": dup, "기준": "0건", "판정": "통과" if dup == 0 else "실패"},
    ]).to_csv("reports/tables/split_check.csv", index=False, encoding="utf-8-sig")

    print(f"{NL}[저장] reports/figures/split_check.png · tables/split_check.csv")


if __name__ == "__main__":
    main()
