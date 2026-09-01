# =====================================================================
# Day1 층화분할 결과(train/test)를 DB에 올리는 스크립트
#
# 사용법: python db/load_split.py <사용자명> <비밀번호> [DB명]
# 예:     python db/load_split.py pioneer4 ****** ABC8pioneer4
#
# 왜 필요한가:
#   분할 결과가 로컬 CSV에 '행 번호'로만 저장돼 있어서 DB에서는 쓸 수 없다.
#   행 번호를 gameId로 바꿔 테이블에 넣어야 뷰에서 학습셋만 골라낼 수 있다.
#   분할을 DB에 고정해 두면 누가 어디서 조회하든 같은 학습셋을 본다(누수 방지).
#
# 설계 포인트:
#   - 비밀번호는 하드코딩하지 않고 실행 인자로 받는다 (load_mysql.py 와 동일)
#   - upsert 방식이라 여러 번 실행해도 결과가 같다 (기존 행을 지우지 않는다)
# =====================================================================
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다


import pandas as pd
import pymysql

HOST, PORT = "mis.iptime.org", 13306
CSV = "data/high_diamond_ranked_10min.csv"
TRAIN_IDX = "data/splits/train_idx.csv"
TEST_IDX = "data/splits/test_idx.csv"

user, pw = sys.argv[1], sys.argv[2]
db = sys.argv[3] if len(sys.argv) > 3 else "ABC8pioneer4"

# ---------- 1. 행 번호 -> gameId 매핑 ----------
# CSV 를 읽은 순서가 곧 행 번호다. Day1 이 저장한 인덱스가 이 순서를 가리킨다.
df = pd.read_csv(CSV)
train_idx = set(pd.read_csv(TRAIN_IDX)["idx"])
test_idx = set(pd.read_csv(TEST_IDX)["idx"])

# 검증: 겹치지 않아야 하고, 합이 전체 행수와 같아야 한다
assert not (train_idx & test_idx), "train/test 인덱스가 겹칩니다"
assert len(train_idx) + len(test_idx) == len(df), "인덱스 합이 전체 행수와 다릅니다"

rows = [(int(df.at[i, "gameId"]), "train" if i in train_idx else "test")
        for i in range(len(df))]
n_tr = sum(1 for _, s in rows if s == "train")
print(f"매핑 생성: 전체 {len(rows)} = train {n_tr} + test {len(rows) - n_tr}")

# ---------- 2. 테이블 생성 후 적재 ----------
conn = pymysql.connect(host=HOST, port=PORT, user=user, password=pw, database=db)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ml_split (
    gameId BIGINT      NOT NULL PRIMARY KEY,
    split  VARCHAR(5)  NOT NULL,
    INDEX idx_split (split)
) COMMENT='Day1 층화분할 결과 (seed=42). 학습셋 고정용'
""")

# upsert: 이미 있으면 값만 갱신 -> 재실행해도 같은 상태가 된다
cur.executemany(
    "INSERT INTO ml_split (gameId, split) VALUES (%s, %s) "
    "ON DUPLICATE KEY UPDATE split = VALUES(split)",
    rows,
)
conn.commit()

# ---------- 3. 적재 검증 3종 ----------
cur.execute("SELECT split, COUNT(*) FROM ml_split GROUP BY split ORDER BY split")
print("적재 결과:", dict(cur.fetchall()))

cur.execute("""
SELECT COUNT(*) FROM lol_matches_10min m
LEFT JOIN ml_split s ON m.gameId = s.gameId
WHERE s.gameId IS NULL
""")
missing = cur.fetchone()[0]
print(f"분할이 안 붙은 경기: {missing}건 {'(정상)' if missing == 0 else '(문제!)'}")

cur.execute("""
SELECT s.split, ROUND(AVG(m.blueWins), 4)
FROM lol_matches_10min m JOIN ml_split s ON m.gameId = s.gameId
GROUP BY s.split ORDER BY s.split
""")
print("층화 확인(양쪽 승률이 비슷해야 함):", dict(cur.fetchall()))

conn.close()
