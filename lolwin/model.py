"""모델 정의와 학습 — "이 모델이 어디서 나왔나" 를 파일만 보고 알 수 있게 한다.

한 함수(`train`)가 적재 → 학습 → 평가 → 저장을 순서대로 하고,
산출물에 데이터 지문·시드·패키지 버전·git 커밋을 함께 남긴다.
지금까지는 학습 절차가 src/finalize_model.py 안에 그림 그리기와 섞여 있어
"모델만 다시 만들기" 가 어려웠다.
"""
from __future__ import annotations

import json
import os
import subprocess

from lolwin.features import DIFF13

SEED = 42
"""모든 무작위성의 기준값. 바꾸면 모델이 달라진다."""


def make_pipeline(seed: int = SEED):
    """StandardScaler + LogisticRegression 을 한 덩어리로.

    Pipeline 으로 묶는 이유는 두 가지다.
    ① 교차검증의 각 폴드 안에서 스케일러가 그 폴드의 학습 부분으로만 fit 된다(누수 방지).
    ② 저장할 때 통째로 저장되어, 예측할 때 표준화를 빠뜨릴 수가 없다.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000, random_state=seed)),
    ])


def _git_commit() -> str | None:
    """어느 코드로 학습했는지. git 이 없거나 저장소가 아니면 None."""
    try:
        from lolwin.artifacts import ROOT

        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def evaluate(pipe, X_te, y_te) -> dict:
    """봉인 해제 — 시험지로 딱 한 번 채점한다."""
    from sklearn.metrics import (accuracy_score, brier_score_loss,
                                 confusion_matrix, f1_score, roc_auc_score)

    proba = pipe.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    cm = confusion_matrix(y_te, pred)
    return {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "f1": round(float(f1_score(y_te, pred)), 4),
        "auc": round(float(roc_auc_score(y_te, proba)), 4),
        "brier": round(float(brier_score_loss(y_te, proba)), 4),
        "baseline_accuracy": round(float(max(y_te.mean(), 1 - y_te.mean())), 4),
        "confusion_matrix": {"TN": int(cm[0, 0]), "FP": int(cm[0, 1]),
                             "FN": int(cm[1, 0]), "TP": int(cm[1, 1])},
    }


def cross_validate_stability(pipe, X_tr, y_tr, seed: int = SEED) -> dict:
    """운이 아닌지 확인 — 5조각으로 5번."""
    from sklearn.model_selection import StratifiedKFold, cross_validate

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    res = cross_validate(pipe, X_tr, y_tr, cv=cv, scoring=["accuracy", "f1"],
                         return_train_score=True, n_jobs=1)
    acc, std = float(res["test_accuracy"].mean()), float(res["test_accuracy"].std())
    gap = float(res["train_accuracy"].mean()) - acc
    return {
        "cv_accuracy": round(acc, 4), "cv_std": round(std, 4),
        "train_minus_cv": round(gap, 4),
        "stable": bool(std < 0.02), "not_overfit": bool(gap < 0.03),
        # 원본 폴드별 점수 — runs.csv 기록처럼 표준편차까지 필요한 곳에서 쓴다
        "raw": res,
    }


def train(source: str | None = None, seed: int = SEED, out_dir: str | None = None,
          verbose: bool = True) -> dict:
    """적재 → 교차검증 → 학습 → 평가 → 저장. 산출물 경로와 성능을 돌려준다.

    out_dir 을 주면 그쪽에 쓴다(검증용). 안 주면 artifacts/ 에 쓴다.
    """
    import joblib
    import pandas as pd
    import sklearn

    from lolwin import data
    from lolwin.artifacts import ARTIFACTS

    out_dir = out_dir or ARTIFACTS
    os.makedirs(out_dir, exist_ok=True)

    X_tr, y_tr, X_te, y_te, dmeta = data.load(source)
    if verbose:
        print(f"[데이터] {dmeta['data_source']} — 학습 {len(y_tr):,} / 시험 {len(y_te):,}")

    pipe = make_pipeline(seed)
    stab = cross_validate_stability(pipe, X_tr, y_tr, seed)
    if verbose:
        print(f"[교차검증] {stab['cv_accuracy']:.4f} ± {stab['cv_std']:.4f} · "
              f"격차 {stab['train_minus_cv']:+.4f} · "
              f"{'통과' if stab['stable'] and stab['not_overfit'] else '기준 위반'}")

    pipe.fit(X_tr, y_tr)
    metrics = evaluate(pipe, X_te, y_te)
    if verbose:
        cm = metrics["confusion_matrix"]
        print(f"[홀드아웃] acc {metrics['accuracy']:.4f} · F1 {metrics['f1']:.4f} · "
              f"AUC {metrics['auc']:.4f} · Brier {metrics['brier']:.4f}")
        print(f"[혼동행렬] TN {cm['TN']} FP {cm['FP']} / FN {cm['FN']} TP {cm['TP']}")

    model_path = os.path.join(out_dir, "model.joblib")
    joblib.dump(pipe, model_path)

    # 저장한 것이 그대로 복원되는지 — 저장 형식이 바뀌면 여기서 걸린다
    restored = joblib.load(model_path)
    assert (restored.predict_proba(X_te[:50])
            == pipe.predict_proba(X_te[:50])).all(), "저장·복원 후 예측이 달라졌습니다"

    schema = {
        "model_name": "LoL 승패 예측·설명 서비스",
        "version": "1.0",
        "time_point_min": 10,
        "target": "blueWins (블루팀 승리 확률)",
        "feature_set": "diff13 (블루-레드 차이, 양수=블루 우세)",
        "trained_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "data_source": dmeta["data_source"],
        "sklearn_version": sklearn.__version__,
        "seed": seed,
        "metrics_holdout": {k: v for k, v in metrics.items() if k != "confusion_matrix"},
        # type 은 실제 dtype 으로 판정한다. 하드코딩하면 AvgLevelDiff(실수)가
        # int 로 적혀 쓰는 쪽이 잘못된 입력 검증을 하게 된다.
        "features": {
            f: {"type": "int" if pd.api.types.is_integer_dtype(X_tr[f]) else "float",
                "train_min": float(X_tr[f].min()),
                "train_max": float(X_tr[f].max()),
                "train_mean": round(float(X_tr[f].mean()), 3)}
            for f in DIFF13
        },
        # ── 이력(provenance) — 이 모델이 어디서 나왔나 ──────────────
        "provenance": {
            "data_hash": dmeta.get("data_hash"),
            "split_hash": dmeta.get("split_hash"),
            "n_train": dmeta["n_train"], "n_test": dmeta["n_test"],
            "git_commit": _git_commit(),
            "cv": {k: v for k, v in stab.items() if k != "raw"},
            "confusion_matrix": metrics["confusion_matrix"],
        },
    }
    schema_path = os.path.join(out_dir, "schema.json")
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"[저장] {os.path.relpath(model_path)} · {os.path.relpath(schema_path)}")
    return {"model_path": model_path, "schema_path": schema_path,
            "metrics": metrics, "cv": stab, "schema": schema}


if __name__ == "__main__":
    train()
