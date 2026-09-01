# =====================================================================
# Day 2 — 중복 피처 정리 · 차이 피처 · PCA · 군집화
#
# 실행 방법: 프로젝트 폴더에서  python src/day2_features_cluster.py
# 선행 조건: day1_baseline.py 를 먼저 실행 (분할 인덱스 파일을 재사용함)
#
# 이 스크립트가 하는 일:
#   1. Day1 에서 찾은 완전 중복 9쌍 제거 (39피처 → 30피처)
#   2. "블루 − 레드 차이" 피처 14개 생성 (피처 엔지니어링)
#   3. 두 피처 세트를 같은 조건으로 비교 → 어느 쪽을 쓸지 데이터로 결정
#   4. PCA 로 데이터 구조 해석 (우세가 몇 종류의 축으로 이루어졌나)
#   5. KMeans 군집 (→ 결과가 자명해서 day2b 에서 재설계함. 실패도 기록으로 남김)
# =====================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()   # 어디서 실행하든 프로젝트 폴더 기준으로 맞춘다 (경로 오류 방지)

import time
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # 그림을 화면 대신 파일로 저장
import matplotlib.pyplot as plt
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

SEED = 42
df = pd.read_csv("data/high_diamond_ranked_10min.csv").drop(columns=["gameId"])
y = df["blueWins"]

# ---------- 1. 중복 피처 정리 (Day1 실측 9쌍 근거) ----------
# 상관 ±1.0 = 완전히 같은 정보가 두 번 들어간 것.
# 종류별 이유를 주석에 남긴다 (나중에 "왜 지웠지?" 를 코드만 보고 알 수 있게)
drop_dup = [
    "redFirstBlood",            # = 1 - blueFirstBlood (첫 킬은 한 팀만 가능)
    "redGoldDiff",              # = -blueGoldDiff      (부호만 반대인 미러)
    "redExperienceDiff",        # = -blueExperienceDiff
    "redKills", "redDeaths",    # = blueDeaths, blueKills (내 킬 = 상대 데스)
    "blueGoldPerMin", "redGoldPerMin",      # = TotalGold ÷ 10 (10분 시점이라)
    "blueCSPerMin", "redCSPerMin",          # = TotalMinionsKilled ÷ 10
    # 2026-08-31 추가 발견 — 세 컬럼의 합 관계라 1차 상관 검사에서 놓쳤다
    "blueEliteMonsters", "redEliteMonsters",  # = Dragons + Heralds (VIF 무한대)
]
clean = df.drop(columns=drop_dup)
print(f"[정리] 원본 39피처 -> 중복 {len(drop_dup)}개 제거 -> {clean.shape[1]-1}피처")

# ---------- 2. 차이 피처 세트 (블루 - 레드) ----------
# 아이디어: 게임의 본질은 "격차 싸움"(스노우볼) 이므로
# 양 팀의 절대값보다 '차이'가 승패를 더 직접적으로 표현할 것이다.
# 장점: 피처 수가 절반으로 줄고, 해석이 "양수 = 블루 우세"로 단순해진다.
pairs = ["WardsPlaced", "WardsDestroyed", "Assists", "Dragons",
         "Heralds", "TowersDestroyed", "AvgLevel", "TotalMinionsKilled",
         "TotalJungleMinionsKilled"]
diff = pd.DataFrame(index=df.index)
diff["FirstBlood"] = df["blueFirstBlood"]          # 이미 0/1 로 대칭 정보를 담음
diff["KillsDiff"] = df["blueKills"] - df["redKills"]
diff["GoldDiff"] = df["blueGoldDiff"]              # 원본에 이미 차이로 존재
diff["ExpDiff"] = df["blueExperienceDiff"]
for p in pairs:
    diff[f"{p}Diff"] = df[f"blue{p}"] - df[f"red{p}"]
print(f"[차이 피처] {diff.shape[1]}개 생성: {list(diff.columns)}")

# ---------- 3. 두 피처 세트로 로지스틱 재확인 (분할 인덱스 재사용) ----------
# Day1 이 저장한 훈련 인덱스를 읽어 '같은 시험지' 조건을 유지한다.
# 피처 세트만 바꾸고 나머지(분할·모델·검증)는 고정 → 통제된 비교.
tr_idx = pd.read_csv("data/splits/train_idx.csv")["idx"].values
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
runs = []


def evaluate(name, X_all):
    """피처 세트 하나를 (표준화 + 로지스틱) 파이프라인으로 5-fold 평가."""
    X_tr, y_tr = X_all.loc[tr_idx], y.loc[tr_idx]  # 훈련셋만 사용 (테스트는 봉인 유지)
    pipe = Pipeline([("scaler", StandardScaler()),
                     ("model", LogisticRegression(max_iter=1000, random_state=SEED))])
    t0 = time.time()
    res = cross_validate(pipe, X_tr, y_tr, cv=cv,
                         scoring=["accuracy", "f1"], return_train_score=True, n_jobs=1)
    elapsed = time.time() - t0
    runs.append((name, res, elapsed))
    print(f"[점수] {name}: acc {res['test_accuracy'].mean():.4f} ± {res['test_accuracy'].std():.4f} | "
          f"F1 {res['test_f1'].mean():.4f} | train_acc {res['train_accuracy'].mean():.4f} | {elapsed:.2f}s")


evaluate("logreg_clean27", clean.drop(columns=["blueWins"]))  # 중복 11개 제거
evaluate(f"logreg_diff{diff.shape[1]}", diff)                 # 차이 피처 14개
# → 실측: 0.7344 vs 0.7369 — 절반 크기로 소폭 우세 → 차이 피처 채택

# ---------- 4. PCA — 학습셋 기준, 차이 피처 표준화 후 ----------
# PCA = 여러 피처를 "요약 축(주성분)" 몇 개로 압축하는 방법.
# 반드시 표준화 후에 (단위가 큰 골드가 축을 독점하는 것을 막기 위해).
# scaler 를 학습셋으로만 fit 하는 것도 누수 방지 습관.
Xd_tr = diff.loc[tr_idx]
scaler = StandardScaler().fit(Xd_tr)
Z_tr = scaler.transform(Xd_tr)

pca = PCA(random_state=SEED).fit(Z_tr)
evr = pca.explained_variance_ratio_   # 각 주성분이 설명하는 분산 비율
cum = np.cumsum(evr)
n90 = int(np.argmax(cum >= 0.9)) + 1  # 누적 90% 를 넘는 최소 주성분 수
print(f"\n[PCA] PC1 {evr[0]:.1%} · PC2 {evr[1]:.1%} · 누적 90%까지 {n90}개 주성분")

# 적재량(loading) = 각 주성분이 원래 피처를 얼마나 반영하는가.
# 이걸 읽고 축에 '이름'을 붙인다 (PC1=성장 우세 축, PC2=오브젝트 축).
load = pd.DataFrame(pca.components_[:2].T, index=diff.columns, columns=["PC1", "PC2"])
print("[PCA] PC1 적재량 상위(절대값):")
print(load["PC1"].sort_values(key=abs, ascending=False).head(6).round(3).to_string())
print("[PCA] PC2 적재량 상위(절대값):")
print(load["PC2"].sort_values(key=abs, ascending=False).head(6).round(3).to_string())

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].bar(range(1, 11), evr[:10])                       # 막대 = 주성분별 설명력
ax[0].plot(range(1, 11), cum[:10], "o-", color="tab:red")  # 선 = 누적 설명력
ax[0].set_title("PCA explained variance (top 10)")
ax[0].set_xlabel("PC")

# ---------- 5. KMeans 군집 — k 선택(실루엣) 후 프로파일 ----------
# 실루엣 점수 = 군집이 얼마나 잘 뭉치고 잘 떨어졌는가 (1에 가까울수록 좋음).
# sample_size=3000 : 전수 계산은 느려서 표본으로 근사.
P2 = pca.transform(Z_tr)[:, :2]  # 그림용 2차원 좌표
sil = {}
for k in range(2, 8):
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z_tr)
    sil[k] = silhouette_score(Z_tr, km.labels_, sample_size=3000, random_state=SEED)
print("\n[군집] k별 실루엣:", {k: round(v, 3) for k, v in sil.items()})
best_k = max(sil, key=sil.get)
print(f"[군집] 선택 k = {best_k}")

km = KMeans(n_clusters=best_k, n_init=10, random_state=SEED).fit(Z_tr)
lab = km.labels_

sc = ax[1].scatter(P2[:, 0], P2[:, 1], c=lab, s=4, cmap="tab10", alpha=0.5)
ax[1].set_title(f"KMeans k={best_k} on PCA plane")
ax[1].set_xlabel("PC1")
ax[1].set_ylabel("PC2")
fig.tight_layout()
fig.savefig("reports/day2_pca_cluster.png", dpi=120)

# 군집 프로파일 = 군집별 평균값 표. "각 군집이 어떤 경기들의 모임인지" 읽는 도구.
key_cols = ["GoldDiff", "ExpDiff", "KillsDiff", "DragonsDiff", "HeraldsDiff",
            "TowersDestroyedDiff", "WardsPlacedDiff"]
prof = Xd_tr.copy()
prof["cluster"] = lab
prof["blueWins"] = y.loc[tr_idx].values
profile = prof.groupby("cluster").agg(
    n=("blueWins", "size"), blue_winrate=("blueWins", "mean"),
    **{c: (c, "mean") for c in key_cols}).round(2)
profile["share_%"] = (profile["n"] / profile["n"].sum() * 100).round(1)
print("\n[군집 프로파일] (학습셋 기준, 값은 블루-레드 차이의 평균)")
print(profile.to_string())
profile.to_csv("reports/day2_cluster_profile.csv")
# ★ 교훈: 이 군집은 k=2 로 "블루 우세 vs 레드 우세"(승률 73%/27%)가 나왔다.
#   정답을 되비추는 '자명한 군집'이라 새 정보가 없음.
#   → day2b_game_types.py 에서 진영 정보를 지운 피처로 재설계했다.

# ---------- 6. 기록 ----------
# 열 순서는 runlog.py 한 곳에서만 정의한다 (열 어긋남 사고 방지)
from runlog import log_run

for _name, _res, _sec in runs:
    log_run(_name, _res, _sec)
print("\n[기록] runs.csv 추가 · reports/day2_pca_cluster.png · day2_cluster_profile.csv 저장")
