"""데이터 적재 — DB 우선, 없으면 CSV 폴백. 경로는 패키지 기준으로 잡는다.

작업 디렉터리에 의존하지 않는다. 라이브러리가 남의 cwd 를 가정하면
다른 폴더에서 부르는 순간 조용히 실패하기 때문이다.
"""
from __future__ import annotations

import hashlib
import os

from lolwin.artifacts import ROOT
from lolwin.features import TARGET, build

CSV_PATH = os.path.join(ROOT, "data", "high_diamond_ranked_10min.csv")
TRAIN_IDX = os.path.join(ROOT, "data", "splits", "train_idx.csv")
TEST_IDX = os.path.join(ROOT, "data", "splits", "test_idx.csv")


def file_hash(path: str, n: int = 12) -> str:
    """파일 내용의 지문. '이 모델이 어느 데이터로 학습됐나' 를 나중에 확인하려고 남긴다."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def load(source: str | None = None):
    """(X_tr, y_tr, X_te, y_te, meta) — 학습에 쓸 재료 일체.

    source: "db" | "csv" | None(자동 — DB_PASSWORD 가 있으면 db)

    ★ gameId 로 정렬하는 이유 — DB 뷰가 ORDER BY gameId 로 읽으므로 행 순서를 맞춘다.
      StratifiedKFold(shuffle=True) 는 입력 행 순서에 따라 폴드를 다르게 나누기 때문에,
      순서가 다르면 같은 데이터인데 CV 점수가 미세하게 달라진다
      (실측: 정렬 안 하면 0.7367, 정렬하면 0.7369).
    """
    import pandas as pd

    use_db = (source == "db") or (source is None and os.environ.get("DB_PASSWORD"))
    if use_db:
        import sys

        sys.path.insert(0, os.path.join(ROOT, "src"))
        from load_from_db import load as db_load

        X_tr, y_tr = db_load("diff13", "train")
        X_te, y_te = db_load("diff13", "test")
        from lolwin.features import DIFF13

        meta = {"data_source": "db:v_diff13", "data_hash": None,
                "n_train": len(y_tr), "n_test": len(y_te)}
        return X_tr[DIFF13], y_tr, X_te[DIFF13], y_te, meta

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"{CSV_PATH} 가 없습니다 — data/README.md 의 링크에서 받으세요")

    df = pd.read_csv(CSV_PATH).sort_values("gameId")
    X, y = build(df), df[TARGET]

    # day1 이 저장한 분할 인덱스를 그대로 쓴다. 순서까지 같아야 CV 폴드가 재현된다.
    tr = pd.read_csv(TRAIN_IDX)["idx"].values
    te = pd.read_csv(TEST_IDX)["idx"].values
    overlap = set(tr) & set(te)
    if overlap:
        raise ValueError(f"train/test 인덱스가 {len(overlap)}건 겹칩니다 — 분할이 깨졌습니다")

    meta = {
        "data_source": "csv:fallback",
        "data_hash": file_hash(CSV_PATH),
        "split_hash": f"{file_hash(TRAIN_IDX, 8)}/{file_hash(TEST_IDX, 8)}",
        "n_train": len(tr), "n_test": len(te),
    }
    return X.loc[tr], y.loc[tr], X.loc[te], y.loc[te], meta
