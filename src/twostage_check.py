# 2단계 라우팅 검증 — "애매한 경기만 전문 모델에 넘기면 접전이 나아지는가"
#
# 실행: python src/twostage_check.py
#
# 아이디어(외부 제안): 1차 로지스틱의 확률이 0.4~0.6 으로 애매하면 판정을 보류하고,
# 경기 유형(군집)을 아는 2차 '접전 특화 모델'에 넘긴다. 유형이라는 맥락을 주면
# 접전 구간 정확도 0.615 를 끌어올릴 수 있지 않겠느냐는 것.
#
# 우리 규칙: 채택 여부는 실측이 정한다. 이 스크립트가 그 실측이다.
#
# 누수 주의 두 가지 —
#   ① 2차 모델을 학습할 "애매한 학습 경기"를 고를 때, 1차 모델이 자기가 학습한
#      데이터에 내는 확률은 과하게 자신만만하다. 그래서 교차검증 밖 예측(OOF)으로 고른다.
#   ② 군집(KMeans)도 학습셋에서만 적합하고, 시험셋은 배정만 받는다.
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from lolwin.data import load
from lolwin.features import DIFF13

SEED = 42
BAND = (0.40, 0.60)          # "애매하다"의 정의 — 제안에 나온 그대로
K_TYPES = 4                  # 경기 유형 수 (day2b 와 동일)


def make_primary():
    """1차 모델 — 채택 모델과 같은 구성 (lolwin/model.py 와 동일 하이퍼파라미터)."""
    return Pipeline([("scaler", StandardScaler()),
                     ("model", LogisticRegression(max_iter=1000, random_state=SEED))])


def cluster_features(raw: pd.DataFrame) -> pd.DataFrame:
    """승패 정보를 지운 유형 피처 5개 — day2b_game_types.py 와 같은 정의."""
    g = pd.DataFrame(index=raw.index)
    g["일방성_골드차"] = raw["blueGoldDiff"].abs()
    g["난타전_총킬"] = raw["blueKills"] + raw["redKills"]
    g["오브젝트_총획득"] = raw[["blueDragons", "blueHeralds",
                               "redDragons", "redHeralds"]].sum(axis=1)
    g["시야전_총와드"] = raw["blueWardsPlaced"] + raw["redWardsPlaced"]
    g["성장_총CS"] = raw["blueTotalMinionsKilled"] + raw["redTotalMinionsKilled"]
    return g


def main():
    X_tr, y_tr, X_te, y_te, _ = load(source="csv")

    # ── 경기 유형: 학습셋으로만 적합, 시험셋은 배정만 (누수 방지 ②) ──
    raw = pd.read_csv("data/high_diamond_ranked_10min.csv")   # 인덱스 = lolwin 과 동일한 행 위치
    g_tr, g_te = cluster_features(raw.loc[X_tr.index]), cluster_features(raw.loc[X_te.index])
    sc = StandardScaler().fit(g_tr)
    km = KMeans(n_clusters=K_TYPES, n_init=10, random_state=SEED).fit(sc.transform(g_tr))
    t_tr = pd.get_dummies(pd.Series(km.predict(sc.transform(g_tr)), index=X_tr.index, name="type"), prefix="유형")
    t_te = pd.get_dummies(pd.Series(km.predict(sc.transform(g_te)), index=X_te.index, name="type"), prefix="유형")
    t_te = t_te.reindex(columns=t_tr.columns, fill_value=0)

    # ── 1차 모델: 전체로 학습, 시험셋 확률 ──
    primary = make_primary().fit(X_tr, y_tr)
    p_te = primary.predict_proba(X_te)[:, 1]
    base_pred = (p_te >= 0.5).astype(int)
    base_acc = accuracy_score(y_te, base_pred)

    # ── 라우팅 대상 고르기: 학습은 OOF 확률로 (누수 방지 ①), 시험은 1차 확률로 ──
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    p_oof = cross_val_predict(make_primary(), X_tr, y_tr, cv=cv, method="predict_proba")[:, 1]
    amb_tr = (p_oof >= BAND[0]) & (p_oof <= BAND[1])
    amb_te = (p_te >= BAND[0]) & (p_te <= BAND[1])
    n_amb_te = int(amb_te.sum())
    sub_base_acc = accuracy_score(y_te[amb_te], base_pred[amb_te])

    print(f"1차 모델(전체): {base_acc:.4f}  ·  애매 구간({BAND[0]}~{BAND[1]}) "
          f"시험 {n_amb_te}판({n_amb_te/len(y_te):.1%}) — 1차의 이 구간 정확도 {sub_base_acc:.4f}")
    print(f"애매 구간 학습 재료: {int(amb_tr.sum())}판 (OOF 기준)\n")

    # ── 2차 후보들: 애매한 학습 경기로만 학습 ──
    def with_types(X, t):
        return pd.concat([X, t.astype(int)], axis=1)

    candidates = {
        "2차: 로지스틱 재학습(13개)": (
            make_primary().fit(X_tr[amb_tr], y_tr[amb_tr]),
            X_te, X_tr, None),
        "2차: 로지스틱+경기유형 원핫": (
            make_primary().fit(with_types(X_tr, t_tr)[amb_tr], y_tr[amb_tr]),
            with_types(X_te, t_te), with_types(X_tr, t_tr), None),
        "2차: HistGB(비선형)": (
            HistGradientBoostingClassifier(random_state=SEED).fit(X_tr[amb_tr], y_tr[amb_tr]),
            X_te, X_tr, None),
        "2차: 유형별 로지스틱 4개": None,     # 아래에서 별도 처리
    }

    rows = []
    for name, spec in candidates.items():
        if spec is not None:
            m, Xe, _, _ = spec
            p2 = m.predict_proba(Xe)[:, 1]
            routed = base_pred.copy()
            routed[amb_te] = (p2[amb_te] >= 0.5).astype(int)
        else:
            # 유형별 개별 모델 — 애매+해당 유형 경기로 각각 학습 (표본이 매우 작아짐)
            routed = base_pred.copy()
            type_tr = km.predict(sc.transform(g_tr))
            type_te = km.predict(sc.transform(g_te))
            for c in range(K_TYPES):
                m_tr = amb_tr & (type_tr == c)
                m_te = amb_te & (type_te == c)
                if m_tr.sum() < 50 or m_te.sum() == 0 or y_tr[m_tr].nunique() < 2:
                    continue                    # 표본 부족 유형은 1차 판정 유지
                mm = make_primary().fit(X_tr[m_tr], y_tr[m_tr])
                routed[m_te] = mm.predict(X_te[m_te])
        rows.append({
            "구성": name,
            "전체 정확도": round(accuracy_score(y_te, routed), 4),
            "애매 구간 정확도": round(accuracy_score(y_te[amb_te], routed[amb_te]), 4),
            "전체 변화": round(accuracy_score(y_te, routed) - base_acc, 4),
            "애매 구간 변화": round(accuracy_score(y_te[amb_te], routed[amb_te]) - sub_base_acc, 4),
        })

    out = pd.DataFrame([{"구성": "1차 단일 모델 (현재)", "전체 정확도": round(base_acc, 4),
                         "애매 구간 정확도": round(sub_base_acc, 4),
                         "전체 변화": 0.0, "애매 구간 변화": 0.0}] + rows)
    print(out.to_string(index=False))

    os.makedirs("reports/tables", exist_ok=True)
    out.to_csv("reports/tables/twostage_check.csv", index=False, encoding="utf-8-sig")
    print("\n[저장] reports/tables/twostage_check.csv")

    # ── 반복 검증: 분할을 5번 바꿔도 같은 결론인가 ──
    # 위 결과는 고정 분할 하나의 값이다. 운이 아닌지, 분할부터 다시 하며
    # 가장 단순한 2차(로지스틱 재학습)로 5회 반복한다.
    from sklearn.model_selection import train_test_split

    X_all = pd.concat([X_tr, X_te])
    y_all = pd.concat([y_tr, y_te])
    deltas_all, deltas_amb = [], []
    for seed in range(5):
        Xa, Xb, ya, yb = train_test_split(X_all, y_all, test_size=0.2,
                                          stratify=y_all, random_state=seed)
        pri = make_primary().fit(Xa, ya)
        pb = pri.predict_proba(Xb)[:, 1]
        bp = (pb >= 0.5).astype(int)
        cv2 = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        po = cross_val_predict(make_primary(), Xa, ya, cv=cv2, method="predict_proba")[:, 1]
        a_tr = (po >= BAND[0]) & (po <= BAND[1])
        a_te = (pb >= BAND[0]) & (pb <= BAND[1])
        st2 = make_primary().fit(Xa[a_tr], ya[a_tr])
        rp = bp.copy()
        rp[a_te] = st2.predict(Xb[a_te])
        deltas_all.append(accuracy_score(yb, rp) - accuracy_score(yb, bp))
        deltas_amb.append(accuracy_score(yb[a_te], rp[a_te]) - accuracy_score(yb[a_te], bp[a_te]))

    print(f"\n[반복 5회 — 분할을 바꿔도] 전체 변화 {np.mean(deltas_all):+.4f} ± {np.std(deltas_all):.4f}"
          f" · 애매 구간 변화 {np.mean(deltas_amb):+.4f} ± {np.std(deltas_amb):.4f}")
    worse = sum(1 for d in deltas_amb if d <= 0)
    print(f"  애매 구간이 나빠지거나 그대로인 횟수: {worse}/5")


if __name__ == "__main__":
    main()
