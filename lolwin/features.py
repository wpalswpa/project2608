"""피처 정의 — 이 파일이 유일한 정본이다.

지금까지 피처 목록과 계산식이 finalize_model.py · db/create_ml_views.sql ·
predict.py 에 흩어져 있어, 한쪽만 고치면 조용히 어긋났다(실제로 계수 수치가 갈렸다).
앞으로 피처를 바꾸려면 **여기만** 고치고 `python -m lolwin.features --sql` 로
SQL 뷰를 다시 뽑는다.

import 만으로는 아무 부작용도 없다 — 작업 디렉터리를 바꾸거나 파일을 읽지 않는다.
"""
from __future__ import annotations

TIME_POINT_MIN = 10
"""이 피처 묶음이 보는 시점(분). 15분 데이터를 쓰려면 이 값과 원천만 바꾼다."""

TARGET = "blueWins"
"""정답 컬럼 — 1 이면 블루 팀 승리."""

# 블루 − 레드 차이로 통일한 13개. 전부 "양수 = 블루 우세" 로 방향이 같다.
# 순서가 곧 모델 입력 순서이므로 함부로 바꾸면 저장된 모델과 어긋난다.
DIFF13: tuple[str, ...] = (
    "FirstBlood", "KillsDiff", "GoldDiff", "ExpDiff", "WardsPlacedDiff",
    "WardsDestroyedDiff", "AssistsDiff", "DragonsDiff", "HeraldsDiff",
    "TowersDestroyedDiff", "AvgLevelDiff", "TotalMinionsKilledDiff",
    "TotalJungleMinionsKilledDiff",
)

# 원본 컬럼이 blue*/red* 쌍으로 있어 그대로 빼면 되는 것들
_PAIRED = (
    "WardsPlaced", "WardsDestroyed", "Assists", "Dragons", "Heralds",
    "TowersDestroyed", "AvgLevel", "TotalMinionsKilled", "TotalJungleMinionsKilled",
)

# 원본 이름이 규칙에서 벗어나 따로 적어야 하는 것들
_SPECIAL = {
    "FirstBlood": ("blueFirstBlood", None),          # 0/1 이라 이미 대칭 — 차이 계산 불필요
    "KillsDiff": ("blueKills", "redKills"),
    "GoldDiff": ("blueGoldDiff", None),              # 원본이 이미 차이값
    "ExpDiff": ("blueExperienceDiff", None),         # 〃
}

KOREAN: dict[str, str] = {
    "GoldDiff": "골드(돈) 차이", "ExpDiff": "경험치 차이", "KillsDiff": "킬 차이",
    "FirstBlood": "첫 킬", "WardsPlacedDiff": "와드 설치 차이",
    "WardsDestroyedDiff": "와드 제거 차이", "AssistsDiff": "어시스트 차이",
    "DragonsDiff": "드래곤 차이", "HeraldsDiff": "전령 차이",
    "TowersDestroyedDiff": "타워 파괴 차이", "AvgLevelDiff": "평균 레벨 차이",
    "TotalMinionsKilledDiff": "미니언(CS) 차이",
    "TotalJungleMinionsKilledDiff": "정글 몬스터 차이",
}


def build(df):
    """원본 40컬럼 표 → 차이 피처 13개 표.

    SQL 뷰 `v_diff13_*` 와 같은 계산식이며, 그 SQL 도 이 정의에서 생성한다(`to_sql`).
    """
    import pandas as pd

    out = pd.DataFrame(index=df.index)
    for name, (blue, red) in _SPECIAL.items():
        out[name] = df[blue] if red is None else df[blue] - df[red]
    for p in _PAIRED:
        out[f"{p}Diff"] = df[f"blue{p}"] - df[f"red{p}"]
    return out[list(DIFF13)]


def to_sql(view: str = "v_diff13_all", source: str = "v_base") -> str:
    """같은 계산식을 SQL 뷰로 뽑는다 — 파이썬과 SQL 이 어긋날 수 없게 하기 위해서다.

    `db/create_ml_views.sql` 의 v_diff13_all 과 같은 내용이어야 하며,
    `sql_matches_file()` 이 그것을 확인한다.
    """
    body = ",\n".join([
        "    gameId",
        f"    {TARGET} AS y",
        *[f"    {sql_expr(n)} AS {n}" for n in DIFF13],
        "    split",
    ])
    return f"CREATE OR REPLACE VIEW {view} AS\nSELECT\n{body}\nFROM {source};\n"


def sql_expr(name: str) -> str:
    """피처 하나의 SQL 표현식."""
    if name in _SPECIAL:
        blue, red = _SPECIAL[name]
        return blue if red is None else f"{blue} - {red}"
    p = name[:-4]  # "…Diff" 에서 Diff 를 뗀다
    return f"blue{p} - red{p}"


def sql_matches_file(path: str = "db/create_ml_views.sql") -> list[str]:
    """SQL 파일의 v_diff13_all 이 이 정의와 같은지 확인. 어긋난 항목을 돌려준다.

    파이썬 쪽만 고치고 SQL 을 안 고치면 DB 로 학습할 때 값이 달라진다.
    오류가 안 나고 숫자만 조용히 바뀌므로 기계로 잡아야 한다.
    """
    import io
    import re

    text = io.open(path, encoding="utf-8").read()
    m = re.search(r"CREATE OR REPLACE VIEW\s+v_diff13_all\s+AS(.*?);", text, re.S | re.I)
    if not m:
        return [f"{path} 에서 v_diff13_all 뷰를 찾지 못했습니다"]

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    block = norm(m.group(1))
    bad = []
    for n in DIFF13:
        want = norm(f"{sql_expr(n)} as {n}")
        if want not in block:
            bad.append(f"{n}: SQL 에 `{sql_expr(n)} AS {n}` 이 없습니다")
    return bad


def validate(payload: dict) -> list[str]:
    """예측 입력에 빠진 피처 이름 목록 (비어 있으면 정상)."""
    return [f for f in DIFF13 if f not in payload]


if __name__ == "__main__":
    import sys

    if "--sql" in sys.argv:
        print(to_sql())
    else:
        print(f"피처 {len(DIFF13)}개 · 시점 {TIME_POINT_MIN}분 · 정답 {TARGET}")
        for i, f in enumerate(DIFF13, 1):
            print(f"  {i:2}. {f:30} {KOREAN[f]}")
