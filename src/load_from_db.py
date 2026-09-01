# 학습용 데이터셋 로더 — 피처셋별 DB 뷰에서 (X, y) 를 읽어온다
#
# 사용:
#   from load_from_db import load
#   X_tr, y_tr = load("diff13", "train")     # 7,903행 × 13피처
#
# 단독 실행(전 뷰 행수·피처수 확인):
#   python src/load_from_db.py
#
# 규칙 (data_io.py 와 동일):
#   - 비밀번호는 코드에 넣지 않는다. 환경변수 DB_PASSWORD 로만 전달
#   - 피처 정의는 SQL 뷰 한 곳에만 둔다. 여기서는 읽기만 한다.
#     같은 계산식을 파이썬에 또 짜면 두 곳이 갈라져도 아무도 모른다.
import os

import pandas as pd

# 접속 정보는 환경변수로 받는다 (공개 저장소에 서버 주소를 남기지 않는다)
HOST = os.environ.get("DB_HOST", "localhost")
PORT = int(os.environ.get("DB_PORT", 3306))
USER = os.environ.get("DB_USER", "root")
DB = os.environ.get("DB_NAME", "lol_db")

# 피처셋 -> (피처 수, 설명). 뷰 이름은 v_<피처셋>_<split>
FEATURE_SETS = {
    "diff13":   (13, "차이 피처 — 현재 채택 (CV 정확도 0.7369)"),
    "clean27":  (27, "중복 11개 제거 — 차이 변환의 대조군"),
    "gold2":    (2,  "골드차+경험치차만 (0.7328) — 최소 기준"),
    "cluster5": (5,  "군집용 사이드 중립 — 비지도, y 없음"),
}
SPLITS = ("train", "test", "all")

EXPECTED_ROWS = {"train": 7903, "test": 1976, "all": 9879}


def load(feature_set: str, split: str = "train"):
    """뷰에서 (X, y) 를 읽어온다. cluster5 는 y 가 없어 (X, None) 을 준다."""
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"모르는 피처셋: {feature_set} (가능: {list(FEATURE_SETS)})")
    if split not in SPLITS:
        raise ValueError(f"모르는 분할: {split} (가능: {SPLITS})")

    pw = os.environ.get("DB_PASSWORD")
    if not pw:
        raise RuntimeError("DB_PASSWORD 환경변수가 없습니다. 예: $env:DB_PASSWORD='...'")

    import pymysql
    view = f"v_{feature_set}_{split}"
    conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=pw,
                           database=DB, connect_timeout=10)
    try:
        df = pd.read_sql(f"SELECT * FROM `{view}` ORDER BY gameId", conn)
    finally:
        conn.close()

    # 식별자·분할 라벨은 피처가 아니므로 뺀다
    y = df.pop("y") if "y" in df.columns else None
    X = df.drop(columns=[c for c in ("gameId", "split") if c in df.columns])

    n_expected = FEATURE_SETS[feature_set][0]
    assert X.shape[1] == n_expected, f"{view}: 피처 {X.shape[1]}개 != 기대 {n_expected}개"
    assert len(X) == EXPECTED_ROWS[split], f"{view}: {len(X)}행 != 기대 {EXPECTED_ROWS[split]}행"
    print(f"[load_from_db] {view} — {len(X):,}행 × {X.shape[1]}피처 로드·검증 완료")
    return X, y


if __name__ == "__main__":
    print(f"{'피처셋':<10} {'분할':<6} {'행':>7} {'피처':>5}  설명")
    print("-" * 76)
    for fs, (n, desc) in FEATURE_SETS.items():
        for sp in ("train", "test"):
            if fs == "cluster5" and sp == "test":
                continue  # cluster5 는 train 뷰만 만들어 둠
            X, _ = load(fs, sp)
            print(f"{fs:<10} {sp:<6} {len(X):>7,} {X.shape[1]:>5}  "
                  f"{desc if sp == 'train' else ''}")
