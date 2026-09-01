# =====================================================================
# Day 1 — 첫 점검 · EDA · 층화 분할 · 베이스라인
#
# 실행 방법: 프로젝트 폴더에서  python src/day1_baseline.py
#
# 이 스크립트가 하는 일 (가이드라인 1~6항목):
#   1. 데이터 첫 점검  — 크기 / 결측 / 정답(y) 분포 확인
#   2. EDA            — 정답과의 상관 순위, 완전 중복 피처 쌍 찾기, 그림 저장
#   3. 층화 분할      — 공부용 80% / 봉인 시험용 20% 로 나누고 인덱스 저장
#   4. 베이스라인     — "찍기 점수"를 먼저 재고, 첫 모델(로지스틱)과 비교
#   5. 실험 기록      — 결과를 runs.csv 에 한 줄씩 남김 (재현성 규약)
#
# 이 순서가 중요한 이유: "분할이 전처리보다 먼저" (누수 방지 규칙 1번).
# 시험지(테스트셋)의 정보가 공부 과정에 새어 들어가면
# 오류 없이 점수만 오르는 가짜 성능이 나온다.
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

matplotlib.use("Agg")  # 화면 없이 파일로만 그림 저장 (서버/터미널 환경용)
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_validate, StratifiedKFold
from sklearn.dummy import DummyClassifier          # "찍기" 베이스라인 모델
from sklearn.pipeline import Pipeline              # 전처리+모델을 한 덩어리로
from sklearn.preprocessing import StandardScaler   # 표준화 (평균0, 표준편차1)
from sklearn.linear_model import LogisticRegression

SEED = 42  # 난수 시드 고정 — 누가 언제 돌려도 같은 결과 (재현성 규약 1번)
DATA = "data/high_diamond_ranked_10min.csv"  # 절대경로 금지 (재현성 규약 3번)

# ★ gameId 순으로 정렬한다 (재현성 규약 8번, 2026-09-01 추가)
#   train_test_split 과 StratifiedKFold(shuffle=True) 는 시드가 같아도
#   "입력 행의 순서"가 다르면 다르게 나눈다. DB 뷰는 ORDER BY gameId 로 읽으므로
#   CSV 도 같은 순서로 맞춰야 DB/CSV 어느 쪽으로 돌려도 같은 결과가 나온다.
#   (이 정렬을 빼먹었을 때 홀드아웃이 0.7394 대신 0.7136 으로 나왔다 — 실험보고 11장)
df = pd.read_csv(DATA).sort_values("gameId")

# ---------- 1. 첫 점검 3가지 ----------
# 왜 이 셋부터 보나:
#   크기  → 데이터가 몇 행인지에 따라 쓸 수 있는 방법이 달라진다
#   결측  → 있으면 처리 방식(대치/삭제)을 정해야 한다
#   y분포 → 균형/불균형에 따라 평가지표(정확도 vs F1)가 달라진다
print("=" * 60)
print("[첫 점검] shape:", df.shape)                      # (행, 열)
print("[첫 점검] 결측 합계:", int(df.isna().sum().sum()))  # 0이면 결측 처리 불필요
print("[첫 점검] y 분포 (blueWins):")
print(df["blueWins"].value_counts(normalize=True).round(4).to_string())
# → 실측 결과 50.1 : 49.9 균형 → "정확도를 1순위 지표로 써도 된다"는 근거

# ID·상수 컬럼 제거 (규칙 0번)
# gameId 는 경기의 '이름표'일 뿐 정보가 아니다. 안 지우면 모델이 외운다(암기).
# nunique()==1 인 컬럼(상수)은 정보량이 0이라 함께 제거 대상.
const_cols = [c for c in df.columns if df[c].nunique() == 1]
drop_cols = ["gameId"] + const_cols
print("[첫 점검] 제거 컬럼:", drop_cols)
df = df.drop(columns=drop_cols)

# ---------- 2. EDA (탐색적 데이터 분석) ----------
# 모델을 돌리기 전에 데이터를 눈으로 먼저 본다.
# 초급자의 최대 실수 = 모델링부터 시작하는 것.
y = df["blueWins"]
X = df.drop(columns=["blueWins"])

# (a) 정답과의 상관 순위 — "어떤 피처가 승패와 관련이 깊은가"의 첫 힌트
#     key=abs : 음의 상관(-0.5)도 강한 관계이므로 절대값 기준으로 정렬
corr = X.corrwith(y).sort_values(key=abs, ascending=False)
print("\n[EDA] blueWins 상관 상위 10:")
print(corr.head(10).round(3).to_string())
# → 실측: 골드차(0.51) > 경험치차(0.49) — "킬보다 돈"이라는 가설의 근거

# (b) 피처끼리의 상관이 ±1.0 인 쌍 = 완전 중복 (같은 정보가 두 번 들어감)
#     블루/레드 대칭 구조 때문에 생긴다. 예: blueKills == redDeaths
#     그대로 두면 중요도 해석이 왜곡됨 → Day2에서 제거할 목록을 여기서 확정
cm = X.corr()
dup_pairs = []
cols = cm.columns
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        if abs(cm.iloc[i, j]) > 0.999:  # 부동소수점 오차 감안해 0.999 초과
            dup_pairs.append((cols[i], cols[j], round(cm.iloc[i, j], 3)))
print("\n[EDA] 상관 ±1.0 완전 중복 쌍 (Day2 정리 대상):")
for p in dup_pairs:
    print("  ", p)

# (c) 그림 저장: 상관 순위 막대 + 핵심 피처의 승/패별 분포 비교

os.makedirs("reports", exist_ok=True)
fig, ax = plt.subplots(figsize=(8, 8))
corr.head(20)[::-1].plot.barh(ax=ax)  # [::-1] : 큰 값이 위로 오게 뒤집기
ax.set_title("Correlation with blueWins (top 20)")
fig.tight_layout()
fig.savefig("reports/figures/eda_corr_top20.png", dpi=120)

# 승리 경기(파란색)와 패배 경기(빨간색)의 분포가 얼마나 갈리는지 눈으로 확인
fig, axes = plt.subplots(2, 2, figsize=(10, 7))
for a, col in zip(axes.ravel(), ["blueGoldDiff", "blueExperienceDiff", "blueKills", "blueTotalGold"]):
    for v, c in [(1, "tab:blue"), (0, "tab:red")]:
        a.hist(df.loc[y == v, col], bins=40, alpha=0.5, color=c, label=f"blueWins={v}")
    a.set_title(col)
    a.legend(fontsize=8)
fig.tight_layout()
fig.savefig("reports/figures/eda_hist_key_features.png", dpi=120)
print("\n[EDA] 그림 저장: reports/figures/eda_corr_top20.png, reports/figures/eda_hist_key_features.png")

# ---------- 3. 층화 분할 (분할이 전처리보다 먼저!) ----------
# stratify=y : 훈련/시험 양쪽의 승/패 비율을 똑같이 유지 (층화 분할)
# test_size=0.2 : 20%는 봉인된 시험지 — 마지막 평가 때까지 열지 않는다
X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.2, random_state=SEED, stratify=y
)
# 분할 결과를 파일로 저장 (재현성 규약 2번)
# → 이후 어떤 스크립트든 같은 인덱스를 읽어 "같은 시험지"로 평가할 수 있다
os.makedirs("data/splits", exist_ok=True)
pd.DataFrame({"idx": X_tr.index}).to_csv("data/splits/train_idx.csv", index=False)
pd.DataFrame({"idx": X_te.index}).to_csv("data/splits/test_idx.csv", index=False)
print(f"\n[분할] train {X_tr.shape} / test {X_te.shape} (봉인) — 인덱스 저장 완료")

# ---------- 4. 베이스라인 + 첫 모델 (5-fold CV, 학습·검증 병기) ----------
# StratifiedKFold : 교차검증의 각 조각(fold)에서도 승/패 비율 유지
# 교차검증을 쓰는 이유 : 시험 1번은 운일 수 있다 → 5번 보고 평균±표준편차로 보고
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
runs = []  # 실험 결과를 모았다가 runs.csv 에 기록


def evaluate(name, pipeline):
    """모델 하나를 훈련셋에서 5-fold 교차검증하고 결과를 출력·기록한다.

    return_train_score=True : 학습 점수도 함께 받는다.
    학습 점수와 검증 점수를 '나란히' 봐야 과적합(암기)을 진단할 수 있다.
    (학습만 높고 검증이 낮으면 = 외운 것)
    """
    t0 = time.time()
    res = cross_validate(
        pipeline, X_tr, y_tr, cv=cv,
        scoring=["f1", "accuracy"], return_train_score=True, n_jobs=1,  # 1코어 환경
    )
    elapsed = time.time() - t0
    runs.append((name, res, elapsed))
    print(f"[점수] {name}: acc {res['test_accuracy'].mean():.4f} ± {res['test_accuracy'].std():.4f} | "
          f"F1 {res['test_f1'].mean():.4f} | {elapsed:.2f}s")


print("\n" + "=" * 60)
# 베이스라인 ① 한쪽으로만 찍기 : 다수 클래스만 예측.
#   균형 데이터라 정확도는 약 0.50 이 나오지만,
#   "승리"를 한 번도 예측하지 않으므로 F1 은 0 이 된다 (지표별 베이스라인이 다른 사례)
evaluate("baseline_dummy_most_frequent",
         DummyClassifier(strategy="most_frequent"))
# 베이스라인 ② 비율대로 랜덤 찍기 : F1 비교용 기준선 (약 0.50)
evaluate("baseline_dummy_stratified",
         DummyClassifier(strategy="stratified", random_state=SEED))
# 첫 모델: 표준화 + 로지스틱 회귀
#   Pipeline 에 넣는 이유 = 교차검증의 각 fold 안에서 스케일러가
#   그 fold 의 학습 부분으로만 fit 되도록 보장 (전처리 누수 방지)
evaluate("logreg_standardized",
         Pipeline([("scaler", StandardScaler()),
                   ("model", LogisticRegression(max_iter=1000, random_state=SEED))]))

# ---------- 5. 실험 기록 (재현성 규약 7번: 실험은 runs.csv 에) ----------
# 열 순서는 runlog.py 한 곳에서만 정의한다 (열 어긋남 사고 방지)
from runlog import log_run

for _name, _res, _sec in runs:
    log_run(_name, _res, _sec)
print("\n[기록] runs.csv 저장 완료 — Day1 목표(점수 찍힌 결과) 달성 여부는 위 표로 확인")
