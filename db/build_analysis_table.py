# =====================================================================
# 분석용 통합 테이블 lol_analysis_10min 을 만든다
#
# 사용법: python db/build_analysis_table.py <사용자명> <비밀번호> [DB명]
#
# 왜 뷰가 아니라 테이블인가:
#   뷰로 계산되는 것(차이 피처·중립 피처)은 이미 v_* 뷰에 있다.
#   이 테이블이 추가로 담는 것은 **뷰로는 만들 수 없는 파생 결과** —
#   KMeans 로 구한 '경기 유형' 라벨이다. SQL 만으로는 군집을 못 돌린다.
#   그래서 한 번 계산해 고정(스냅샷)해 두고, 누구나 SQL 로 조회하게 한다.
#
# 주의 (누수 방지):
#   군집은 **학습셋에서만 적합**하고, 시험셋은 그 모델로 예측만 한다.
#   시험셋을 포함해 다시 적합하면 봉인이 깨진다.
# =====================================================================
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다


import pandas as pd
import pymysql
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

SEED = 42
HOST, PORT = "mis.iptime.org", 13306
CSV = "data/high_diamond_ranked_10min.csv"
TABLE = "lol_analysis_10min"

user, pw = sys.argv[1], sys.argv[2]
db = sys.argv[3] if len(sys.argv) > 3 else "ABC8pioneer4"

df = pd.read_csv(CSV)
tr_idx = pd.read_csv("data/splits/train_idx.csv")["idx"].values
te_idx = pd.read_csv("data/splits/test_idx.csv")["idx"].values

# ---------- 1. 차이 피처 13개 (모델 입력) ----------
# EliteMonsters 제외: = Dragons + Heralds 라 완전한 선형 종속 (2026-08-31 발견)
PAIRS = ["WardsPlaced", "WardsDestroyed", "Assists", "Dragons",
         "Heralds", "TowersDestroyed", "AvgLevel", "TotalMinionsKilled",
         "TotalJungleMinionsKilled"]

feat = pd.DataFrame(index=df.index)
feat["FirstBlood"] = df["blueFirstBlood"]
feat["KillsDiff"] = df["blueKills"] - df["redKills"]
feat["GoldDiff"] = df["blueGoldDiff"]
feat["ExpDiff"] = df["blueExperienceDiff"]
for p in PAIRS:
    feat[f"{p}Diff"] = df[f"blue{p}"] - df[f"red{p}"]

# ---------- 2. 사이드 중립 피처 5개 (군집 입력) ----------
def neutral(d):
    g = pd.DataFrame(index=d.index)
    g["oneSidedGold"] = d["blueGoldDiff"].abs()              # 얼마나 기울었나
    g["totalKills"] = d["blueKills"] + d["redKills"]          # 싸움 빈도
    g["totalObjects"] = d[["blueDragons", "blueHeralds",
                           "redDragons", "redHeralds"]].sum(axis=1)
    g["totalWards"] = d["blueWardsPlaced"] + d["redWardsPlaced"]
    g["totalCS"] = d["blueTotalMinionsKilled"] + d["redTotalMinionsKilled"]
    return g

g_tr, g_all = neutral(df.loc[tr_idx]), neutral(df)

# ---------- 3. 경기 유형 군집 — 학습셋 적합 -> 전체 예측 ----------
scaler = StandardScaler().fit(g_tr)
km = KMeans(n_clusters=4, n_init=10, random_state=SEED).fit(scaler.transform(g_tr))

# 군집 번호는 실행마다 뒤바뀌므로 '특징'으로 이름을 정한다 (결정적 규칙)
prof = g_tr.groupby(km.labels_).mean()
names, left = {}, list(prof.index)
for label, col in [("일방적경기", "oneSidedGold"), ("시야전", "totalWards"),
                   ("난타전", "totalKills")]:
    c = prof.loc[left, col].idxmax()
    names[c] = label
    left.remove(c)
names[left[0]] = "운영전"

game_type = pd.Series(km.predict(scaler.transform(g_all)), index=df.index).map(names)

# ---------- 4. 최종 테이블 조립 ----------
out = pd.DataFrame({"gameId": df["gameId"], "y": df["blueWins"]})
out["split"] = "test"
out.loc[tr_idx, "split"] = "train"
out = pd.concat([out, feat, g_all], axis=1)
out["gameType"] = game_type.values

print(f"조립 완료: {out.shape[0]}행 × {out.shape[1]}컬럼")
print("유형 비중(학습셋, %):")
print((out.loc[tr_idx, "gameType"].value_counts(normalize=True) * 100).round(1).to_string())

# ---------- 5. 적재 ----------
cols_int = ["FirstBlood", "KillsDiff", "GoldDiff", "ExpDiff"] + \
           [f"{p}Diff" for p in PAIRS if p != "AvgLevel"] + \
           ["oneSidedGold", "totalKills", "totalObjects", "totalWards", "totalCS"]

ddl = [f"gameId BIGINT NOT NULL PRIMARY KEY",
       "y TINYINT NOT NULL",
       "split VARCHAR(5) NOT NULL"]
for c in out.columns:
    if c in ("gameId", "y", "split", "gameType"):
        continue
    ddl.append(f"`{c}` " + ("INT" if c in cols_int else "DOUBLE") + " NOT NULL")
ddl += ["gameType VARCHAR(12) NOT NULL", "INDEX idx_split (split)",
        "INDEX idx_type (gameType)"]

conn = pymysql.connect(host=HOST, port=PORT, user=user, password=pw, database=db)
cur = conn.cursor()
cur.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (\n  " + ",\n  ".join(ddl) +
            "\n) COMMENT='분석용 통합 스냅샷: 차이피처13 + 중립피처5 + 경기유형(KMeans seed42)'")

cols = list(out.columns)
ph = ", ".join(["%s"] * len(cols))
upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in cols if c != "gameId")
rows = [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
              for v in r) for r in out.itertuples(index=False)]
cur.executemany(
    f"INSERT INTO {TABLE} ({', '.join('`'+c+'`' for c in cols)}) VALUES ({ph}) "
    f"ON DUPLICATE KEY UPDATE {upd}", rows)
conn.commit()

# ---------- 6. 적재 검증 ----------
cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
print(f"\n적재 행수: {cur.fetchone()[0]:,} (기대 {len(out):,})")
cur.execute(f"SELECT split, COUNT(*), ROUND(AVG(y),4) FROM {TABLE} GROUP BY split ORDER BY split")
print("분할별:", cur.fetchall())
cur.execute(f"""SELECT gameType, COUNT(*) n, ROUND(AVG(y),3) 블루승률,
                       ROUND(AVG(oneSidedGold)) 평균골드차
                FROM {TABLE} WHERE split='train'
                GROUP BY gameType ORDER BY 평균골드차""")
print("유형별(학습셋):")
for r in cur.fetchall():
    print("   ", r)
conn.close()
