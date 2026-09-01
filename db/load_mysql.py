# =====================================================================
# CSV -> MariaDB 적재 스크립트
#
# 사용법: python db/load_mysql.py <사용자명> <비밀번호> [DB명]
# 예:     python db/load_mysql.py pioneer4 ****** ABC8pioneer4
#
# 설계 포인트:
#   - 비밀번호는 코드에 하드코딩하지 않고 실행 인자로 받는다 (보안 습관)
#   - 컬럼 타입은 이름 패턴으로 자동 결정 (ID=BIGINT, 0/1=TINYINT, 소수=DOUBLE)
#   - 한 행씩 INSERT 하면 느리므로 1,000행씩 배치(executemany)로 적재
#   - 적재 후 행 수·대표 통계를 원본과 대조 (적재 검증 3종)
# =====================================================================
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다

import csv

import pymysql

HOST, PORT = "mis.iptime.org", 13306
CSV = "data/high_diamond_ranked_10min.csv"
TABLE = "lol_matches_10min"

# 명령 인자: [1]=사용자명, [2]=비밀번호, [3]=DB명(생략 시 ABC8pioneer4)
user, pw = sys.argv[1], sys.argv[2]
db = sys.argv[3] if len(sys.argv) > 3 else "ABC8pioneer4"

# ---------- 1. CSV 읽기 ----------
with open(CSV, encoding="utf-8") as f:
    reader = csv.reader(f)
    cols = next(reader)              # 첫 줄 = 컬럼명 (헤더)
    rows = [tuple(r) for r in reader]  # 나머지 = 데이터 행
print(f"CSV: {len(rows)}행 × {len(cols)}컬럼")


def coltype(c):
    """컬럼명 패턴으로 DB 타입을 결정한다.

    gameId          -> BIGINT  (자릿수 큰 고유번호)
    Wins/FirstBlood -> TINYINT (0/1 플래그)
    AvgLevel/PerMin -> DOUBLE  (소수값)
    나머지          -> INT     (킬 수, 골드 등 정수 카운트)
    """
    if c == "gameId":
        return "BIGINT"
    if c in ("blueWins", "blueFirstBlood", "redFirstBlood"):
        return "TINYINT"
    if "AvgLevel" in c or "PerMin" in c:
        return "DOUBLE"
    return "INT"


# ---------- 2. 테이블 생성 (DDL) ----------
# 백틱(`)으로 감싸는 이유: 컬럼명이 예약어와 겹쳐도 안전하게 처리
ddl = ",\n".join(f"  `{c}` {coltype(c)}" for c in cols)
conn = pymysql.connect(host=HOST, port=PORT, user=user, password=pw,
                       database=db, connect_timeout=10)
cur = conn.cursor()
cur.execute(f"DROP TABLE IF EXISTS `{TABLE}`")  # 재실행 시 처음부터 다시 (멱등성)
# gameId 를 기본키(PRIMARY KEY)로 — 같은 경기가 두 번 들어가는 것을 DB가 막아준다
cur.execute(f"CREATE TABLE `{TABLE}` (\n{ddl},\n  PRIMARY KEY (`gameId`)\n)")

# ---------- 3. 배치 INSERT ----------
# %s 플레이스홀더 방식: 값을 문자열로 직접 붙이지 않아 SQL 인젝션·따옴표 문제가 없다
ins = f"INSERT INTO `{TABLE}` ({', '.join(f'`{c}`' for c in cols)}) " \
      f"VALUES ({', '.join(['%s'] * len(cols))})"
for i in range(0, len(rows), 1000):        # 1,000행씩 끊어서
    cur.executemany(ins, rows[i:i + 1000])  # 한 번의 왕복으로 묶음 전송
conn.commit()  # 트랜잭션 확정 — 이 줄이 없으면 적재가 저장되지 않는다

# ---------- 4. 적재 검증 ----------
# ① 행 수 = 원본과 일치하는가
# ② blueWins 합 = 블루 승수 (÷행수 ≈ 0.50 이어야 정상, Day1 실측과 대조)
# ③ blueGoldDiff 평균 ≈ 0 (블루/레드 대칭 구조라 0 근처가 정상)
cur.execute(f"SELECT COUNT(*), SUM(blueWins), ROUND(AVG(blueGoldDiff),1) FROM `{TABLE}`")
n, wins, avg_gd = cur.fetchone()
print(f"적재 완료: {db}.{TABLE} — {n}행, blueWins 합 {wins}, blueGoldDiff 평균 {avg_gd}")
conn.close()
