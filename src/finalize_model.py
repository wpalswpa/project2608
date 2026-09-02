# 마무리 단계 — 최종 학습(lolwin) + 해석 · 오류 분석 · 그림
#
# 실행: 프로젝트 폴더에서  python src/finalize_model.py
#
# 학습 자체는 lolwin.model.train() 이 한다. 이 스크립트는 그 위에서
# "발표에 쓸 해석과 그림" 만 만든다. 예전에는 학습 절차와 그림 그리기가 한 함수에
# 섞여 있어 모델만 다시 만들 수가 없었다.
#
#   학습·저장·이력  → lolwin/model.py   (재현성은 tests/test_training_reproducible.py 가 검사)
#   피처 정의       → lolwin/features.py (정본)
#   여기            → 승리요인 순위, 구간별 오류 분석, 그림
#
# ⚠️ 이걸 실행하면 artifacts/ 가 새로 쓰인다(trained_at 갱신).
#    그러면 tests/golden_predictions.json 도 다시 만들어야 한다:
#      python tests/make_golden.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (그림·CSV 저장 경로)

import time

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 라벨 (Windows)
plt.rcParams["axes.unicode_minus"] = False

from sklearn.inspection import permutation_importance

from lolwin.data import load as load_data
from lolwin.features import DIFF13, GOLD_BIN_LABELS, GOLD_BINS
from lolwin.model import SEED, make_pipeline, train

# 기존 코드가 이 이름들을 import 하던 흔적 — 라이브러리로 옮겼다
TIME_POINT = 10


def main():
    t0 = time.time()

    # ---- 1. 학습·평가·저장은 라이브러리에 맡긴다 ----
    result = train(verbose=True)
    metrics = result["metrics"]
    acc = metrics["accuracy"]

    # ---- 2. 해석용으로 같은 조건에서 다시 맞춘다 (시험지 예측이 필요하므로) ----
    X_tr, y_tr, X_te, y_te, _ = load_data()
    pipe = make_pipeline(SEED).fit(X_tr, y_tr)
    pred = (pipe.predict_proba(X_te)[:, 1] >= 0.5).astype(int)

    # ---- 3. 승리요인 — 표준화 계수 × permutation importance 교차 확인 ----
    coefs = pd.Series(pipe.named_steps["model"].coef_[0], index=DIFF13)
    perm = permutation_importance(pipe, X_te, y_te, n_repeats=10,
                                  random_state=SEED, scoring="accuracy", n_jobs=1)
    imp = pd.Series(perm.importances_mean, index=DIFF13)
    rank = pd.DataFrame({
        "coef_std": coefs.round(4),
        "coef_rank": coefs.abs().rank(ascending=False).astype(int),
        "perm_importance": imp.round(4),
        "perm_rank": imp.rank(ascending=False).astype(int),
    }).sort_values("perm_rank")
    top6 = len(set(rank.nsmallest(6, "coef_rank").index)
               & set(rank.nsmallest(6, "perm_rank").index))
    print(f"\n[승리요인] 두 방법 상위 6개 중 {top6}개 일치 "
          f"(기준 5개 이상: {'충족' if top6 >= 5 else '미달'})")
    print(rank.to_string())
    rank.to_csv("reports/tables/win_factor_ranking.csv", encoding="utf-8-sig")

    # ---- 4. 오류 분석 — 골드차 구간별 정확도 ("접전일수록 틀린다" 검증) ----
    err = pd.DataFrame({"abs_gold": X_te["GoldDiff"].abs().values,
                        "correct": (pred == y_te.values).astype(int)})
    # 구간 경계는 lolwin/features.py 가 정본 — 화면(web/app.py)도 같은 값을 쓴다
    err["구간"] = pd.cut(err["abs_gold"], bins=GOLD_BINS, labels=GOLD_BIN_LABELS, right=False)
    ea = err.groupby("구간", observed=True).agg(경기수=("correct", "size"),
                                                정확도=("correct", "mean")).round(4)
    ea["비중_%"] = (ea["경기수"] / ea["경기수"].sum() * 100).round(1)
    print("\n[오류 분석] 골드차 구간별 홀드아웃 정확도:")
    print(ea.to_string())
    ea.to_csv("reports/tables/day4_error_analysis.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(7, 4))
    ea["정확도"].plot.bar(ax=ax, color="tab:blue")
    ax.axhline(acc, color="tab:red", ls="--", label=f"전체 {acc:.3f}")
    ax.axhline(0.5, color="gray", ls=":", label="찍기 0.5")
    ax.set_title("골드차 구간별 정확도 (홀드아웃)")
    ax.legend()
    fig.tight_layout()
    fig.savefig("reports/figures/day4_error_analysis.png", dpi=120)

    # ---- 5. 실험 기록 (열 순서는 runlog.py 한 곳에서만 정의) ----
    from runlog import log_run

    log_run(f"final_logreg_diff13_holdout(src={result['schema']['data_source']})",
            result["cv"]["raw"], time.time() - t0)
    print("[기록] runs.csv 추가")
    print("\n⚠️ artifacts/ 가 새로 쓰였습니다 — 정답지도 다시 만드세요:")
    print("   python tests/make_golden.py")


if __name__ == "__main__":
    main()
