# 데이터 입출력 유틸 — MariaDB 우선, CSV 폴백
#
# 사용:
#   from data_io import load_matches
#   df = load_matches()            # DB_PASSWORD 환경변수 있으면 DB, 없으면 CSV
#   df = load_matches("csv")       # 강제 CSV
#
# 규칙:
#   - 비밀번호는 코드에 넣지 않는다. 환경변수 DB_PASSWORD 로만 전달
#   - DB와 CSV 어느 쪽을 읽어도 동일한 DataFrame이 나와야 한다 (행 수 검증 포함)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)

import pandas as pd

HOST, PORT = "mis.iptime.org", 13306
USER, DB, TABLE = "pioneer4", "ABC8pioneer4", "lol_matches_10min"
CSV = "data/high_diamond_ranked_10min.csv"
EXPECTED_ROWS = 9879


def load_matches(source: str = "auto") -> pd.DataFrame:
    """경기 데이터 로드. source: 'auto' | 'db' | 'csv'"""
    pw = os.environ.get("DB_PASSWORD")
    use_db = source == "db" or (source == "auto" and pw)
    if use_db:
        if not pw:
            raise RuntimeError("DB_PASSWORD 환경변수가 없습니다. 예: $env:DB_PASSWORD='...'")
        import pymysql
        conn = pymysql.connect(host=HOST, port=PORT, user=USER,
                               password=pw, database=DB, connect_timeout=10)
        try:
            df = pd.read_sql(f"SELECT * FROM `{TABLE}` ORDER BY gameId", conn)
        finally:
            conn.close()
        origin = f"MariaDB {DB}.{TABLE}"
    else:
        df = pd.read_csv(CSV)
        origin = f"CSV {CSV}"

    assert len(df) == EXPECTED_ROWS, f"행 수 불일치: {len(df)} != {EXPECTED_ROWS} ({origin})"
    assert "blueWins" in df.columns and df["blueWins"].isin([0, 1]).all()
    print(f"[data_io] {origin} — {df.shape[0]}행 × {df.shape[1]}컬럼 로드·검증 완료")
    return df


if __name__ == "__main__":
    load_matches(sys.argv[1] if len(sys.argv) > 1 else "auto")
