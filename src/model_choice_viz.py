# -*- coding: utf-8 -*-
"""발표·문서용 — "왜 이 모델을 골랐나"를 네 장면으로 보여준다.

낱장 4개(README 용)와 합본 1장(서비스 화면 web/templates/index.html 이 참조)을 함께 저장한다.
그림을 고칠 때는 draw_* 하나만 고치면 두 곳에 같이 반영된다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

for f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(f == x.name for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False

BLUE, RED, GRAY, GREEN = "#2f6fe4", "#c0392b", "#9aa5b1", "#2e7d32"
NL = chr(10)

# 8종 비교 실측값 — (이름, 검증점수, 연습점수, 격차, 채택여부)
MODELS = [
    ("로지스틱 회귀", 0.7280, 0.7319, 0.0039, True),
    ("랜덤포레스트", 0.7248, 1.0000, 0.2752, False),
    ("GaussianNB", 0.7238, 0.7253, 0.0015, False),
    ("SVM (RBF)", 0.7223, 0.7614, 0.0391, False),
    ("결정트리(d=4)", 0.7180, 0.7285, 0.0105, False),
    ("KNN (k=25)", 0.7147, 0.7353, 0.0206, False),
    ("HistGB", 0.7140, 0.8527, 0.1387, False),
    ("찍기", 0.5009, 0.5009, 0.0000, False),
]
SHOW = [m for m in MODELS if m[0] != "찍기"]


def draw_scores(ax):
    names = [m[0] for m in MODELS]
    cv = [m[1] for m in MODELS]
    colors = [BLUE if m[4] else (GRAY if m[0] != "찍기" else "#d0d5da") for m in MODELS]
    y = np.arange(len(MODELS))[::-1]
    ax.barh(y, cv, color=colors, height=0.62)
    for i, c in enumerate(cv):
        ax.text(c + 0.006, y[i], f"{c:.4f}", va="center", fontsize=10,
                fontweight="bold" if MODELS[i][4] else "normal")
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=10)
    ax.set_xlim(0.48, 0.79); ax.set_xlabel("검증 점수 (교차검증 정확도)")
    ax.axvline(0.5009, color="#d0d5da", ls=":", lw=1.4)
    ax.text(0.5009, y[0] + 0.75, "찍기 0.5009", fontsize=8.5, color="#888", ha="center")
    ax.set_title("① 점수만 보면 — 위 7개가 다 비슷하다" + NL +
                 "(로지스틱 1위지만 2위와 0.003 차이)", fontsize=12, pad=12)


def draw_train_vs_val(ax):
    x = np.arange(len(SHOW))
    tr = [m[2] for m in SHOW]
    va = [m[1] for m in SHOW]
    ax.bar(x - 0.2, tr, 0.4, label="연습 점수", color="#f0a868")
    ax.bar(x + 0.2, va, 0.4, label="검증 점수", color=BLUE)
    for i, (a, b) in enumerate(zip(tr, va)):
        if a - b > 0.05:
            ax.annotate("", xy=(i, a), xytext=(i, b),
                        arrowprops=dict(arrowstyle="<->", color=RED, lw=1.8))
            ax.text(i + 0.03, (a + b) / 2, f"{a-b:+.3f}", color=RED, fontsize=9.5,
                    fontweight="bold", ha="left")
    ax.set_xticks(x); ax.set_xticklabels([m[0] for m in SHOW], fontsize=8.5, rotation=18)
    ax.set_ylim(0.65, 1.06); ax.set_ylabel("정확도")
    ax.legend(fontsize=9, loc="upper right")
    ax.set_title("② 연습과 검증을 나란히 보면 — 누가 외웠는지 보인다" + NL +
                 "랜덤포레스트는 연습 만점(1.0000)인데 검증에서 0.725", fontsize=12, pad=12)


def draw_gap(ax):
    x = np.arange(len(SHOW))
    gap = [m[3] for m in SHOW]
    ax.bar(x, gap, color=[GREEN if g < 0.03 else RED for g in gap], width=0.55)
    for i, g in enumerate(gap):
        ax.text(i, g + 0.006, f"{g:.4f}", ha="center", fontsize=9.5, fontweight="bold")
    ax.axhline(0.03, color="black", ls="--", lw=1.4)
    ax.text(len(SHOW) - 0.4, 0.036, "허용 기준 0.03", fontsize=9, ha="right")
    ax.set_xticks(x); ax.set_xticklabels([m[0] for m in SHOW], fontsize=8.5, rotation=18)
    ax.set_ylabel("연습 − 검증 격차")
    ax.set_title("③ 격차로 판정 — 초록만 통과" + NL +
                 "랜덤포레스트는 기준의 9배(0.2752)", fontsize=12, pad=12)


def draw_decision(ax):
    ax.axis("off")
    rows = [
        ("모델", "점수", "안 외움", "이유 설명"),
        ("로지스틱 회귀", "1위", "O", "O  가중치를 읽을 수 있다"),
        ("랜덤포레스트", "2위", "X", "X  방향(+/−)을 못 말함"),
        ("GaussianNB", "3위", "O", "X"),
        ("SVM · KNN · 트리 · HistGB", "4위~", "일부 X", "X"),
    ]
    t = ax.table(cellText=rows[1:], colLabels=rows[0], cellLoc="left", colLoc="left",
                 loc="upper center", colWidths=[0.34, 0.13, 0.15, 0.38])
    t.auto_set_font_size(False); t.set_fontsize(10.5); t.scale(1, 1.9)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#dde2e8")
        if r == 0:
            cell.set_facecolor(BLUE); cell.set_text_props(color="white", fontweight="bold")
        elif r == 1:
            cell.set_facecolor("#e8f0fd"); cell.set_text_props(fontweight="bold")
    ax.text(0.5, 0.30, "이 프로젝트의 목표는 “왜까지 설명”이다." + NL +
            "점수가 비슷하면 → 설명되는 모델이 맞다.",
            ha="center", fontsize=12.5, fontweight="bold", color="#1a1a1a", transform=ax.transAxes)
    ax.text(0.5, 0.14, "복잡한 모델일수록 점수가 낮았다는 것도 근거가 된다." + NL +
            "10분 정보량이 적어, 복잡한 모델은 배울 게 없어 외우기만 했다.",
            ha="center", fontsize=10.5, color="#555", transform=ax.transAxes)
    ax.set_title("④ 그래서 로지스틱 회귀", fontsize=12, pad=12)


PANELS = [
    ("model_choice_1_scores.png", draw_scores, (8.2, 5.0)),
    ("model_choice_2_overfit.png", draw_train_vs_val, (8.6, 5.0)),
    ("model_choice_3_gap.png", draw_gap, (8.6, 5.0)),
    ("model_choice_4_decision.png", draw_decision, (8.6, 5.0)),
]


def main():
    os.makedirs("reports/figures", exist_ok=True)

    # 낱장 — README 가 하나씩 설명과 함께 싣는다
    for fname, fn, size in PANELS:
        fig, ax = plt.subplots(figsize=size)
        fn(ax)
        fig.tight_layout()
        fig.savefig(f"reports/figures/{fname}", dpi=130, bbox_inches="tight")
        plt.close(fig)
        print(f"저장: reports/figures/{fname}")

    # 합본 — 서비스 화면(web/templates/index.html)이 이 경로를 참조한다
    fig = plt.figure(figsize=(14, 9.5))
    gs = fig.add_gridspec(2, 2, hspace=0.42, wspace=0.26)
    for (_, fn, _), pos in zip(PANELS, [gs[0, 0], gs[0, 1], gs[1, 0], gs[1, 1]]):
        fn(fig.add_subplot(pos))
    fig.suptitle("왜 로지스틱 회귀를 택했나 — 후보 8종, 같은 조건(5조각 교차검증 · 시드 42)",
                 fontsize=14.5, fontweight="bold", y=0.975)
    fig.savefig("reports/06_model_choice.png", dpi=130, bbox_inches="tight")
    print("저장: reports/06_model_choice.png (서비스 화면용 합본)")


if __name__ == "__main__":
    main()
