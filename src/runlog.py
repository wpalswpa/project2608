# 실험 로그 공용 유틸 — runs.csv 의 열 순서를 한 곳에서만 정의한다
#
# 배경: 초기에 스크립트마다 dict 키 순서가 달라 header=False append 시
# 열이 어긋나는 사고가 있었음(2026-08-31 정정). 이후 모든 기록은 이 모듈로만.
import os

import pandas as pd

COLUMNS = ["date", "run", "cv_acc_mean", "cv_acc_std", "cv_f1_mean", "cv_f1_std",
           "train_acc_mean", "train_f1_mean", "sec"]


def log_run(name: str, res: dict, sec: float, path: str = "runs.csv") -> dict:
    """cross_validate 결과(res)를 runs.csv 에 한 줄 기록하고 그 행을 돌려준다."""
    row = {
        "date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "run": name,
        "cv_acc_mean": round(res["test_accuracy"].mean(), 4),
        "cv_acc_std": round(res["test_accuracy"].std(), 4),
        "cv_f1_mean": round(res["test_f1"].mean(), 4),
        "cv_f1_std": round(res["test_f1"].std(), 4),
        "train_acc_mean": round(res["train_accuracy"].mean(), 4),
        "train_f1_mean": round(res["train_f1"].mean(), 4),
        "sec": round(sec, 2),
    }
    pd.DataFrame([row])[COLUMNS].to_csv(
        path, mode="a", index=False, header=not os.path.exists(path))
    return row
