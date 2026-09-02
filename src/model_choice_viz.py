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

# 8종 비교 실측값은 하드코딩하지 않고 근거 파일에서 읽는다.
# 예전에는 이 자리에 숫자가 손으로 적혀 있었고 그 값을 만든 코드가 없었다 —
# 재학습하면 조용히 어긋나므로 src/model_compare.py 가 만든 CSV 를 읽는다.
COMPARISON_CSV = "reports/tables/model_comparison.csv"


def load_models():
    """(이름, 검증점수, 연습점수, 격차, 채택여부) 목록. 검증점수 내림차순."""
    import csv

    if not os.path.exists(COMPARISON_CSV):
        raise SystemExit(f"{COMPARISON_CSV} 가 없습니다 — 먼저 python src/model_compare.py 를 실행하세요")
    rows = list(csv.DictReader(open(COMPARISON_CSV, encoding="utf-8-sig")))
    out = [(r["모델"], float(r["검증정확도"]), float(r["연습정확도"]), float(r["격차"]),
            r["판정"] == "통과" and r["모델"] == "로지스틱 회귀")
           for r in rows]
    # "찍기"는 비교 출발선이라 항상 맨 아래로 내린다
    out.sort(key=lambda m: (m[0] == "찍기", -m[1]))
    return out


MODELS = load_models()
BASELINE = next(m[1] for m in MODELS if m[0] == "찍기")   # 찍기 점수 — 기준선으로 쓴다
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
    ax.axvline(BASELINE, color="#d0d5da", ls=":", lw=1.4)
    ax.text(BASELINE, y[0] + 0.75, f"찍기 {BASELINE:.4f}", fontsize=8.5, color="#888", ha="center")
    top2 = MODELS[0][1] - MODELS[1][1]     # 1위와 2위의 점수 차
    ax.set_title("① 점수만 보면 — 위 7개가 다 비슷하다" + NL +
                 f"(로지스틱 1위지만 2위와 {top2:.3f} 차이)", fontsize=12, pad=12)


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
    rf = next(m for m in SHOW if m[0] == "랜덤포레스트")
    ax.set_title("② 연습과 검증을 나란히 보면 — 누가 외웠는지 보인다" + NL +
                 f"랜덤포레스트는 연습 만점({rf[2]:.4f})인데 검증에서 {rf[1]:.4f}",
                 fontsize=12, pad=12)


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
    rf_gap = next(m[3] for m in SHOW if m[0] == "랜덤포레스트")
    ax.set_title("③ 격차로 판정 — 초록만 통과" + NL +
                 f"랜덤포레스트는 기준의 {rf_gap/0.03:.0f}배({rf_gap:.4f})", fontsize=12, pad=12)


def draw_decision(ax):
    ax.axis("off")
    # 순위·과적합 여부는 CSV 에서, "이유 설명 가능"은 모델의 성질이라 여기서 정한다
    EXPLAINS = {"로지스틱 회귀": "O  가중치를 읽을 수 있다"}
    rank = {m[0]: i + 1 for i, m in enumerate(SHOW)}
    rows = [("모델", "점수", "안 외움", "이유 설명")]
    for m in SHOW[:3]:
        rows.append((m[0], f"{rank[m[0]]}위", "O" if m[3] < 0.03 else "X",
                     EXPLAINS.get(m[0], "X  방향(+/−)을 못 말함" if m[0] == "랜덤포레스트" else "X")))
    rest = [m for m in SHOW[3:]]
    rows.append((" · ".join(m[0].split(" (")[0] for m in rest), f"{rank[rest[0][0]]}위~",
                 "일부 X" if any(m[3] >= 0.03 for m in rest) else "O", "X"))
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
