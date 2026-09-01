# 마무리 단계 — 최종 학습 · 홀드아웃 평가 · 해석 · 오류 분석 · 아티팩트 저장/검증
#
# 실행: 프로젝트 폴더에서  python src/finalize_model.py
#
# 데이터 소스 규칙:
#   1순위 — DB 뷰 v_diff13_* (환경변수 DB_PASSWORD 필요, 피처 정의의 정본)
#   폴백  — 로컬 CSV + 아래 파이썬 계산식 (spec 002 "CSV 폴백")
#   ⚠️ 폴백 계산식은 SQL 뷰와 같아야 한다. DB가 열릴 때 parity 검사를 돌릴 것.
#
# 시점 인자 구조(FR-6): TIME_POINT 만 바꾸면 15분 데이터 확보 시 그대로 재실행.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)

import json
import time

import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 라벨 (Windows)
plt.rcParams["axes.unicode_minus"] = False
import sklearn
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix,
                             f1_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42
TIME_POINT = 10  # 분 — 15분 데이터 확보 시 이 값과 데이터 소스만 바꾼다
DIFF13 = ["FirstBlood", "KillsDiff", "GoldDiff", "ExpDiff", "WardsPlacedDiff",
          "WardsDestroyedDiff", "AssistsDiff", "DragonsDiff", "HeraldsDiff",
          "TowersDestroyedDiff", "AvgLevelDiff", "TotalMinionsKilledDiff",
          "TotalJungleMinionsKilledDiff"]


def build_diff13_from_csv(df: pd.DataFrame) -> pd.DataFrame:
    """CSV 폴백 — SQL 뷰 v_diff13_* 와 같은 계산식 (정본은 db/create_ml_views.sql)"""
    out = pd.DataFrame(index=df.index)
    out["FirstBlood"] = df["blueFirstBlood"]
    out["KillsDiff"] = df["blueKills"] - df["redKills"]
    out["GoldDiff"] = df["blueGoldDiff"]
    out["ExpDiff"] = df["blueExperienceDiff"]
    for p in ["WardsPlaced", "WardsDestroyed", "Assists", "Dragons", "Heralds",
              "TowersDestroyed", "AvgLevel", "TotalMinionsKilled",
              "TotalJungleMinionsKilled"]:
        out[f"{p}Diff"] = df[f"blue{p}"] - df[f"red{p}"]
    return out[DIFF13]


def load_data():
    """(X_tr, y_tr, X_te, y_te, source) — DB 우선, 없으면 CSV 폴백"""
    if os.environ.get("DB_PASSWORD"):
        from load_from_db import load
        X_tr, y_tr = load("diff13", "train")
        X_te, y_te = load("diff13", "test")
        return X_tr[DIFF13], y_tr, X_te[DIFF13], y_te, "db:v_diff13"
    # ★ gameId 순으로 정렬한다 — DB 뷰(load_from_db 가 ORDER BY gameId 로 읽음)와
    #   행 순서를 맞추기 위해서다. StratifiedKFold(shuffle=True) 는 입력 행 순서에 따라
    #   폴드를 다르게 나누므로, 순서가 다르면 같은 데이터인데 CV 점수가 미세하게 달라진다
    #   (실측: 정렬 안 하면 0.7367, 정렬하면 0.7369). 재현성을 위해 순서를 고정한다.
    df = pd.read_csv("data/high_diamond_ranked_10min.csv").sort_values("gameId")
    X, y = build_diff13_from_csv(df), df["blueWins"]
    # day1 이 저장한 순서 그대로 뽑는다(.loc). 이 순서가 곧 분할 당시의 순서이며,
    # CV 폴드 구성이 day1·팀 spec 과 같아진다.
    tr = pd.read_csv("data/splits/train_idx.csv")["idx"].values
    te = pd.read_csv("data/splits/test_idx.csv")["idx"].values
    assert not (set(tr) & set(te)), "train/test 인덱스가 겹칩니다"
    return X.loc[tr], y.loc[tr], X.loc[te], y.loc[te], "csv:fallback"


def main():
    os.makedirs("artifacts", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    X_tr, y_tr, X_te, y_te, source = load_data()
    print(f"[데이터] {source} — train {X_tr.shape} / test {X_te.shape} (봉인 해제: 최종 평가 1회)")

    pipe = Pipeline([("scaler", StandardScaler()),
                     ("model", LogisticRegression(max_iter=1000, random_state=SEED))])

    # ---- 1. 교차검증 (안정성 기준 확인) ----
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    t0 = time.time()
    res = cross_validate(pipe, X_tr, y_tr, cv=cv, scoring=["accuracy", "f1"],
                         return_train_score=True, n_jobs=1)
    cv_acc, cv_std = res["test_accuracy"].mean(), res["test_accuracy"].std()
    gap = res["train_accuracy"].mean() - cv_acc
    print(f"[교차검증] acc {cv_acc:.4f} ± {cv_std:.4f} | 학습-검증 격차 {gap:+.4f} "
          f"| 기준: std<0.02 {'통과' if cv_std < 0.02 else '위반'} · 격차<0.03 "
          f"{'통과' if gap < 0.03 else '위반'}")

    # ---- 2. 최종 학습 + 홀드아웃 평가 (딱 한 번) ----
    pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    acc = accuracy_score(y_te, pred)
    f1 = f1_score(y_te, pred)
    auc = roc_auc_score(y_te, proba)
    brier = brier_score_loss(y_te, proba)
    cm = confusion_matrix(y_te, pred)
    baseline = max(y_te.mean(), 1 - y_te.mean())
    print(f"[홀드아웃] acc {acc:.4f} (기준선 {baseline:.4f}, +{acc-baseline:.4f}) "
          f"| F1 {f1:.4f} | AUC {auc:.4f} | Brier {brier:.4f}")
    print(f"[혼동행렬] TN {cm[0,0]} FP {cm[0,1]} / FN {cm[1,0]} TP {cm[1,1]}")

    # ---- 3. 해석 — 표준화 계수 × permutation importance 교차 확인 ----
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
    top6_overlap = len(set(rank.nsmallest(6, "coef_rank").index)
                       & set(rank.nsmallest(6, "perm_rank").index))
    print(f"\n[승리요인] 두 방법 상위 6개 중 {top6_overlap}개 일치 (기준 5개 이상: "
          f"{'충족' if top6_overlap >= 5 else '미달'})")
    print(rank.to_string())
    rank.to_csv("reports/win_factor_ranking.csv", encoding="utf-8-sig")

    # ---- 4. 오류 분석 (FR-4) — 골드차 구간별 정확도 ----
    err = pd.DataFrame({"abs_gold": X_te["GoldDiff"].abs().values,
                        "correct": (pred == y_te.values).astype(int)})
    bins = [0, 1000, 2500, 4200, np.inf]
    labels = ["접전(<1k)", "우세(1k~2.5k)", "크게 우세(2.5k~4.2k)", "사실상 결정(4.2k+)"]
    err["구간"] = pd.cut(err["abs_gold"], bins=bins, labels=labels, right=False)
    ea = err.groupby("구간", observed=True).agg(경기수=("correct", "size"),
                                                정확도=("correct", "mean")).round(4)
    ea["비중_%"] = (ea["경기수"] / ea["경기수"].sum() * 100).round(1)
    print("\n[오류 분석] 골드차 구간별 홀드아웃 정확도 — '접전일수록 틀린다' 검증:")
    print(ea.to_string())
    ea.to_csv("reports/day4_error_analysis.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(7, 4))
    ea["정확도"].plot.bar(ax=ax, color="tab:blue")
    ax.axhline(acc, color="tab:red", ls="--", label=f"전체 {acc:.3f}")
    ax.axhline(0.5, color="gray", ls=":", label="찍기 0.5")
    ax.set_title("Accuracy by |GoldDiff| bin (holdout)")
    ax.legend()
    fig.tight_layout()
    fig.savefig("reports/day4_error_analysis.png", dpi=120)

    # ---- 5. 아티팩트 — 저장 → 복원 → 일치 assert ----
    joblib.dump(pipe, "artifacts/model.joblib")
    restored = joblib.load("artifacts/model.joblib")
    assert (restored.predict(X_te) == pred).all(), "복원 모델 예측 불일치!"
    print("\n[아티팩트] artifacts/model.joblib 저장·복원·예측 일치 assert 통과")

    schema = {
        "model_name": "LoL 승패 예측·설명 서비스",
        "version": "1.0",
        "time_point_min": TIME_POINT,
        "target": "blueWins (블루팀 승리 확률)",
        "feature_set": "diff13 (블루-레드 차이, 양수=블루 우세)",
        "trained_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "data_source": source,
        "sklearn_version": sklearn.__version__,
        "seed": SEED,
        "metrics_holdout": {"accuracy": round(acc, 4), "f1": round(f1, 4),
                            "auc": round(auc, 4), "brier": round(brier, 4),
                            "baseline_accuracy": round(float(baseline), 4)},
        "features": {c: {
            "type": "int" if pd.api.types.is_integer_dtype(X_tr[c]) else "float",
            "train_min": float(X_tr[c].min()), "train_max": float(X_tr[c].max()),
            "train_mean": round(float(X_tr[c].mean()), 3),
        } for c in DIFF13},
    }
    with open("artifacts/schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print("[아티팩트] artifacts/schema.json 저장 (13피처 허용 범위 = 학습셋 min/max)")

    # ---- 6. 실험 기록 (열 순서는 runlog.py 한 곳에서만 정의) ----
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from runlog import log_run
    log_run(f"final_logreg_diff13_holdout(src={source})", res, time.time() - t0)
    print("[기록] runs.csv 추가 — 마무리 단계 완료. 다음: predict.py 스모크 테스트")


if __name__ == "__main__":
    main()
