# =====================================================================
# Day 2b — 경기 유형 군집 (사이드 중립 관점)
#
# 실행 방법: 프로젝트 폴더에서  python src/day2b_game_types.py
# 선행 조건: day1_baseline.py 실행 (분할 인덱스 재사용)
#
# 왜 이 스크립트가 따로 있나:
#   day2 의 군집은 k=2 "블루 우세 vs 레드 우세"로 갈렸다.
#   이는 정답(승패)을 되비추는 '자명한 결과'라 새 정보가 없다.
#   군집 설계의 핵심은 "무엇을 지우고 묶을 것인가" —
#   여기서는 '누가 이기고 있는지'(부호/진영)를 지우고
#   '이 판이 어떤 성격의 경기였는지'(모양)만 남겨 다시 묶는다.
# =====================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 그림에 한글 라벨을 쓰므로 설치된 한글 글꼴을 찾아 지정한다.
# (없으면 네모(□)로 깨져 나온다 — 실제로 그런 적이 있다)
for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(_f == x.name for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _f
        break
plt.rcParams["axes.unicode_minus"] = False   # 마이너스 부호 깨짐 방지
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

SEED = 42
df = pd.read_csv("data/high_diamond_ranked_10min.csv").drop(columns=["gameId"])
tr_idx = pd.read_csv("data/splits/train_idx.csv")["idx"].values
d = df.loc[tr_idx].copy()  # 군집도 학습셋에서만 (테스트 봉인 유지)

# ---------- 사이드 중립 피처 만들기 ----------
# 절대값(abs)과 양 팀 합(+)만 쓰면 진영 정보(부호)가 사라진다.
# 각 피처는 경기의 '성격' 한 가지씩을 담당한다:
g = pd.DataFrame(index=d.index)
g["일방성_골드차"] = d["blueGoldDiff"].abs()      # 얼마나 기울었나 (방향 무시)
g["난타전_총킬"] = d["blueKills"] + d["redKills"]  # 싸움이 얼마나 잦았나
g["오브젝트_총획득"] = d[["blueDragons", "blueHeralds",
                          "redDragons", "redHeralds"]].sum(axis=1)  # 대형 몬스터 중심?
g["시야전_총와드"] = d["blueWardsPlaced"] + d["redWardsPlaced"]      # 시야 싸움 강도
g["성장_총CS"] = d["blueTotalMinionsKilled"] + d["redTotalMinionsKilled"]  # 조용한 성장?

# KMeans 는 거리 기반이라 표준화 필수 (골드 단위가 킬 단위를 압도하지 않게)
Z = StandardScaler().fit_transform(g)

# ---------- k 선택: 실루엣 점수 훑기 ----------
sil = {}
for k in range(2, 7):
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z)
    sil[k] = silhouette_score(Z, km.labels_, sample_size=3000, random_state=SEED)
print("[유형 군집] k별 실루엣:", {k: round(v, 3) for k, v in sil.items()})

# 실루엣 최고는 k=3(0.219)였지만 k=4(0.211)와 근소한 차이.
# 해석 가능성(유형이 4개일 때 이야기가 더 잘 만들어짐)까지 고려해 팀 판단으로 k=4.
# 가이드라인: "엘보우와 실루엣이 다른 답을 주는 것은 정상" — 최종 판단은 사람이 한다.
K = 4
km = KMeans(n_clusters=K, n_init=10, random_state=SEED).fit(Z)
g2 = g.copy()
g2["cluster"] = km.labels_
g2["blueWins"] = df.loc[tr_idx, "blueWins"].values

# "10분에 골드 앞선 팀이 최종 승리했는가" — 군집별 예측 난이도의 대리 지표.
# (골드차 0 인 극소수 경기는 리드가 없으므로 True 처리해 분모에서 중립화)
gold_leader_won = ((d["blueGoldDiff"] > 0) == (g2["blueWins"] == 1)) | (d["blueGoldDiff"] == 0)
g2["리드팀승률"] = gold_leader_won.values

# ---------- 군집 프로파일: 유형별 특징 + 리드팀 승률 ----------
profile = g2.groupby("cluster").agg(
    n=("blueWins", "size"),
    리드팀승률=("리드팀승률", "mean"),
    **{c: (c, "mean") for c in g.columns}).round(2)
profile["비중_%"] = (profile["n"] / profile["n"].sum() * 100).round(1)
profile = profile.sort_values("일방성_골드차")  # 접전 → 일방적 순으로 정렬해 읽기 쉽게
print("\n[경기 유형 프로파일] (학습셋, 리드팀승률 = 10분에 골드 앞선 팀이 최종 승리한 비율)")
print(profile.to_string())
# encoding="utf-8-sig" : 엑셀에서 한글 컬럼명이 깨지지 않게 BOM 포함 저장
profile.to_csv("reports/tables/day2b_game_type_profile.csv", encoding="utf-8-sig")
# → 실측 해석: 운영전 42%(킬9, 승률68%) / 난타전 32%(킬15, 68%) /
#   시야전 7%(와드 3배, 70%) / 일방적 19%(골드차 4200, ★90%)
#   = 일방적 경기는 10분에 사실상 결판, 접전은 아직 1/3이 뒤집힌다.

# ---------- 그림: 일방성 x 교전 빈도 평면에 4유형 산점도 ----------
# 이 그림이 "유형이 실제로 갈라지는가"를 눈으로 보여준다.
# 색만 칠하면 어느 색이 무슨 유형인지 알 수 없으므로, 군집 번호를 이름으로 바꿔
# 범례를 붙이고 중심점(X)을 함께 찍는다.

# 군집 번호 -> 이름. 프로파일 특징값으로 판정한다 (web/app.py 의 _type_label 과 같은 규칙).
prof = profile.reset_index()
ward_max, gold_max = prof["시야전_총와드"].max(), prof["일방성_골드차"].max()
name_of = {}
for _, r in prof.iterrows():
    if r["시야전_총와드"] == ward_max:
        name_of[int(r["cluster"])] = "시야전"
    elif r["일방성_골드차"] == gold_max:
        name_of[int(r["cluster"])] = "일방적 경기"
    else:
        name_of[int(r["cluster"])] = "난타전" if r["난타전_총킬"] >= 13 else "운영전"

COLORS = {"운영전": "#2f6fe4", "난타전": "#c0392b", "일방적 경기": "#e08a3c", "시야전": "#2e7d32"}
NL = chr(10)

fig, ax = plt.subplots(figsize=(9.5, 6))
for cid, name in name_of.items():
    m = km.labels_ == cid
    share = prof.loc[prof["cluster"] == cid, "비중_%"].iloc[0]
    ax.scatter(g.loc[m, "일방성_골드차"], g.loc[m, "난타전_총킬"],
               s=7, alpha=0.35, color=COLORS[name], label=f"{name} ({share}%)")

# 중심점 — 각 유형이 평균적으로 어디에 있나
for cid, name in name_of.items():
    r = prof.loc[prof["cluster"] == cid].iloc[0]
    ax.scatter(r["일방성_골드차"], r["난타전_총킬"], s=220, marker="X",
               color=COLORS[name], edgecolor="white", linewidth=1.6, zorder=5)
    ax.annotate(name, (r["일방성_골드차"], r["난타전_총킬"]),
                xytext=(0, 16), textcoords="offset points", ha="center",
                fontsize=11, fontweight="bold", color=COLORS[name], zorder=6)

ax.set_xlabel("10분 골드 차이의 절대값  —  오른쪽일수록 한쪽으로 기운 경기")
ax.set_ylabel("양 팀 총 킬  —  위쪽일수록 싸움이 잦은 경기")
ax.set_xlim(0, 8000)
leg = ax.legend(loc="upper right", fontsize=10, framealpha=0.9, markerscale=2.2)
leg.set_title("경기 유형 (X = 중심)", prop={"size": 10})
ax.set_title("경기 유형 4가지 — 승패 정보를 지운 좌표에서 묶은 결과" + NL +
             "오른쪽 끝의 '일방적 경기'만 10분에 이미 결판나 있다", fontsize=13, pad=12)
fig.tight_layout()
fig.savefig("reports/figures/day2b_game_types.png", dpi=130, bbox_inches="tight")
print("\n[저장] reports/tables/day2b_game_type_profile.csv · day2b_game_types.png")
