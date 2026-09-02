# 모델 8종 비교 — "왜 로지스틱인가"의 근거를 실제로 만든다
#
# 실행: 프로젝트 폴더에서  python src/model_compare.py
#
# 왜 이 파일이 필요한가:
#   지금까지 8종 비교 수치는 model_choice_viz.py 안에 손으로 적혀 있었고,
#   그 값을 만든 코드가 저장소에 없었다. 즉 "발표에서 제일 많이 인용하는 표"에
#   근거 파일이 없었다. 재학습하면 조용히 어긋날 수 있어 실험을 복원한다.
#
# 조건은 전부 동일하게 통제한다 — 같은 학습셋, 같은 5조각 교차검증, 같은 시드.
# 그래야 점수 차이를 "모델 차이"라고 말할 수 있다.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

cd_root()

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from lolwin.model import SEED

# ★ 비교 기준은 clean27 이다 (diff13 이 아니다).
#   차이 피처로 합치기 "전" 구성에서 모델을 먼저 고르고, 그다음 피처를 정리했기 때문.
#   diff13 으로 돌리면 값이 달라진다 — 문서의 8종 표는 전부 이 clean27 기준이다.
#   정의는 db/create_ml_views.sql 의 v_clean27_all 과 같다 (중복 11개만 제거한 27개).
CLEAN27 = [
    # 블루 16개
    "blueWardsPlaced", "blueWardsDestroyed", "blueFirstBlood", "blueKills", "blueDeaths",
    "blueAssists", "blueDragons", "blueHeralds", "blueTowersDestroyed", "blueTotalGold",
    "blueAvgLevel", "blueTotalExperience", "blueTotalMinionsKilled",
    "blueTotalJungleMinionsKilled", "blueGoldDiff", "blueExperienceDiff",
    # 레드 11개 (거울·중복 8개는 제외)
    "redWardsPlaced", "redWardsDestroyed", "redAssists", "redDragons", "redHeralds",
    "redTowersDestroyed", "redTotalGold", "redAvgLevel", "redTotalExperience",
    "redTotalMinionsKilled", "redTotalJungleMinionsKilled",
]
CSV_PATH = "data/high_diamond_ranked_10min.csv"
TRAIN_IDX = "data/splits/train_idx.csv"


def load_clean27():
    """clean27 학습셋. 분할은 저장된 인덱스를 그대로 쓴다(시험지는 열지 않는다)."""
    df = pd.read_csv(CSV_PATH).sort_values("gameId")   # DB 뷰와 행 순서를 맞춘다
    tr = pd.read_csv(TRAIN_IDX)["idx"].values
    return df.loc[tr, CLEAN27], df.loc[tr, "blueWins"]

# 과적합 판정선 — 연습 점수와 검증 점수의 격차가 이보다 크면 "외웠다"고 본다
OVERFIT_LIMIT = 0.03

# 후보 8종. 하이퍼파라미터는 각 모델의 통상적인 기본 설정을 쓰고 튜닝하지 않는다
# (튜닝을 시작하면 "어느 모델이 나은가"가 아니라 "누가 더 튜닝했나"가 되기 때문).
CANDIDATES = [
    ("로지스틱 회귀",   LogisticRegression(max_iter=1000, random_state=SEED)),
    ("랜덤포레스트",    RandomForestClassifier(random_state=SEED, n_jobs=1)),
    ("GaussianNB",      GaussianNB()),
    ("SVM (RBF)",       SVC(random_state=SEED)),
    ("결정트리(d=4)",   DecisionTreeClassifier(max_depth=4, random_state=SEED)),
    ("KNN (k=25)",      KNeighborsClassifier(n_neighbors=25)),
    ("HistGB",          HistGradientBoostingClassifier(random_state=SEED)),
    ("찍기",            DummyClassifier(strategy="most_frequent")),
]


def main():
    os.makedirs("reports/tables", exist_ok=True)
    X_tr, y_tr = load_clean27()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)

    print("=" * 72)
    print(f"모델 8종 비교 — clean27 · 학습셋 {len(y_tr):,}판 · 피처 {X_tr.shape[1]}개 · 시드 {SEED}")
    print("=" * 72)
    print(f"{'모델':<16}{'검증':>10}{'±':>9}{'연습':>10}{'격차':>10}  판정")

    rows = []
    for name, est in CANDIDATES:
        # 모든 모델에 같은 전처리(표준화)를 붙인다 — 거리·규제 기반 모델에 필요하고,
        # Pipeline 안에 넣어야 폴드마다 학습 부분으로만 fit 되어 누수가 없다
        pipe = Pipeline([("scaler", StandardScaler()), ("model", est)])
        res = cross_validate(pipe, X_tr, y_tr, cv=cv, scoring="accuracy",
                             return_train_score=True, n_jobs=1)
        val, std = res["test_score"].mean(), res["test_score"].std()
        train = res["train_score"].mean()
        gap = train - val

        if name == "찍기":
            verdict = "비교 출발선"
        elif gap > OVERFIT_LIMIT:
            verdict = "탈락 — 외움"
        else:
            verdict = "통과"
        rows.append({"모델": name, "검증정확도": round(float(val), 4),
                     "표준편차": round(float(std), 4), "연습정확도": round(float(train), 4),
                     "격차": round(float(gap), 4), "판정": verdict})
        print(f"{name:<16}{val:>10.4f}{std:>9.4f}{train:>10.4f}{gap:>+10.4f}  {verdict}")

    df = pd.DataFrame(rows).sort_values("검증정확도", ascending=False)
    df.to_csv("reports/tables/model_comparison.csv", index=False, encoding="utf-8-sig")

    best = df[df["판정"] == "통과"].iloc[0]
    print()
    print(f"→ 과적합 기준({OVERFIT_LIMIT})을 통과한 것 중 1위: {best['모델']} "
          f"({best['검증정확도']:.4f}, 격차 {best['격차']:+.4f})")
    print("  점수만으로는 상위권이 촘촘해 못 고른다. 최종 선택은 '가중치로 이유를 설명할 수 있는가'로 갈렸다.")
    print(f"{os.linesep}[저장] reports/tables/model_comparison.csv")


if __name__ == "__main__":
    main()
