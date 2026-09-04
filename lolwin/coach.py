# 코칭 — "그래서 무엇을 하라"까지 말하는 부분
#
# 진단(어디서 졌나)에서 멈추면 사용자는 여전히 무엇을 바꿔야 할지 모른다.
# 이 모듈은 모델을 거꾸로 돌려 "이걸 이만큼 했다면 승률이 얼마였다"를 계산한다.
#
# ★ 이게 가능한 이유가 곧 로지스틱 회귀를 채택한 이유다.
#   확률이 '계수 x 표준화값'의 합이라, 지표를 바꿨을 때의 승률을 되짚을 수 있다.
#   랜덤포레스트를 골랐다면 이 기능 자체가 없다.
#
# ── 반드시 알아야 할 함정 ────────────────────────────────────────
# 계수를 그대로 쓰면 안 된다. KillsDiff 계수는 -0.107, TotalMinionsKilledDiff 는
# -0.157 이라, "킬을 더 했다면" 을 순진하게 계산하면 승률이 **내려간다**.
# 코칭으로 옮기면 "킬하지 마라 · CS 먹지 마라" 라는 엉터리 지시가 된다.
#
# 이유는 다중공선성이다(README 페이즈 2). 킬·CS 의 가치는 이미 골드에 들어가 있어,
# 골드를 고정한 채 킬만 올리는 것은 **현실에 존재하지 않는 상황**이다.
# 그래서 이 모듈은 지표를 올릴 때 **따라오는 골드도 같이 올린다.**
#   CS +20 만          → 41.8% → 39.4%  (틀림)
#   CS +20 & 골드 +1,018 → 41.8% → 51.9%  (맞음)
from __future__ import annotations

from .features import DIFF13, KOREAN
from .predict import predict

# 지표가 1 늘 때 골드 차이가 평균 얼마나 함께 늘었나 — 학습셋 7,903판 실측.
#
# 주의: 이것은 "미니언 하나가 20골드"라는 게임 수치가 아니라, **이 데이터에서
# 관찰된 동반 변화**다. CS 를 앞선 팀은 대개 킬·오브젝트도 앞서므로 그만큼 크다.
# 인과가 아니라 "이 정도 지표차를 가진 팀은 보통 이만큼 골드차를 가졌다"는 뜻이고,
# 코칭 문구도 그 수준으로만 말한다.
#
# 재현: tests/test_coach.py 가 학습 데이터로 이 값을 다시 재서 대조한다.
GOLD_PER_UNIT = {
    "TotalMinionsKilledDiff": 50.9,
    "KillsDiff": 537.1,
    "AssistsDiff": 323.1,
    "DragonsDiff": 722.0,
    "ExpDiff": 1.1,
}

# "한 판에서 현실적으로 이만큼은 더 할 수 있다" 는 크기.
# 너무 크면 (킬 10개 더) 조언이 공허하고, 너무 작으면 승률 변화가 안 보인다.
COACH_STEP = {
    "TotalMinionsKilledDiff": (20, "10분까지 CS 20개 더"),
    "KillsDiff": (1, "킬 1개 더 (또는 데스 1개 덜)"),
    "AssistsDiff": (2, "한타 참여 2회 더"),
    "DragonsDiff": (1, "드래곤 1마리 더"),
    "ExpDiff": (600, "경험치 600 더 (레벨 약 0.5)"),
}

# verdict 별 처방 — 무엇을 고쳐야 하는지는 판정마다 정반대다.
VERDICT_ADVICE = {
    "역전패": ("앞선 판을 끝내지 못하고 있습니다.",
               "10분에 앞서고도 졌습니다. 앞설 때는 위험을 줄이는 쪽이 낫습니다 — "
               "벌어둔 격차를 드래곤·타워 같은 확실한 이득으로 바꾸고, "
               "무리한 싸움으로 되돌려주지 마세요."),
    "열세패": ("라인전에서 이미 지고 시작합니다.",
               "10분에 밀린 채로 그대로 졌습니다. 후반 운영보다 "
               "**10분까지 버티는 것**이 먼저입니다."),
    "역전승": ("불리해도 살아나는 힘이 있습니다.",
               "10분에 밀렸는데 이겼습니다. 후반 집중력은 강점이니, "
               "초반 손해만 줄이면 훨씬 편해집니다."),
    "우세승": ("앞서서 시작해 그대로 이겼습니다.",
               "10분 우세를 끝까지 지켰습니다. 가장 이상적인 형태이니 "
               "이 판의 초반 운영을 표준으로 삼으세요."),
}


# ── 라인 기준선 — "내 티어가 거품인가" ────────────────────────
# 팀 간 격차 축(레이더)은 티어를 안 가린다 — 아이언과 다이아의 평균이
# 교전 7.5 대 8.4, 성장 38.6 대 34.5 로 사실상 같다(1,399판 실측).
# 경기 양상을 재는 축이라 개인 실력을 못 잡는 것이다.
#
# 그래서 기준선을 밖에서 찾지 않고 **같은 판의 라인 상대**로 잡는다.
# 상대는 나와 같은 티어에 배정된 사람이라, 별도 수집 없이 얻는 동급 표본이다.
# "상대보다 CS 를 얼마나 앞섰나" 가 곧 "내 티어에서 내가 어디쯤인가" 다.
LANE_GRADE = [
    (0.70, "과소평가", "티어보다 잘합니다 — 올라갈 여지가 있습니다"),
    (0.55, "제 실력", "티어에 맞게 하고 있습니다"),
    (0.45, "박빙", "라인전은 반반입니다"),
    (0.00, "거품 주의", "같은 티어 상대에게 밀리고 있습니다"),
]


def lane_baseline(games: list) -> dict | None:
    """라인 상대와 견준 10분 성적 — 별도 기준선 수집이 필요 없다.

    3판 미만이면 None. 판마다 라인 상대가 없을 수 있어(포지션 미기록) 있는 것만 센다.
    """
    lanes = [g.get("lane") for g in games if g.get("lane")]
    if len(lanes) < 3:
        return None
    n = len(lanes)
    cs = sum(l["cs_diff"] for l in lanes) / n
    gold = sum(l["gold_diff"] for l in lanes) / n
    lvl = sum(l["level_diff"] for l in lanes) / n
    # 이겼다/졌다는 골드로 판정한다 — CS 만 보면 정글·서폿이 늘 지는 것으로 나온다
    won = sum(1 for l in lanes if l["gold_diff"] > 0)
    rate = won / n
    grade, why = next((g, w) for th, g, w in LANE_GRADE if rate >= th)
    pos = {}
    for l in lanes:
        pos[l["position"]] = pos.get(l["position"], 0) + 1
    return {
        "n": n, "win_rate": round(rate, 4), "wins": won,
        "cs_diff": round(cs, 1), "gold_diff": round(gold), "level_diff": round(lvl, 2),
        "grade": grade, "why": why,
        "main_position": max(pos, key=pos.get) if pos else None,
        "note": "같은 경기의 라인 상대는 나와 같은 티어에 배정된 사람입니다. "
                "그래서 별도 기준선 없이 '내 티어에서 내가 어디쯤인가' 를 잴 수 있습니다.",
    }


# ── 유저 레이더 — 다섯 축으로 성향을 그린다 ────────────────────
# 축을 고른 기준: ① 사용자가 자기 플레이로 읽을 수 있어야 하고 ② 서로 겹치면 안 된다.
# 학습셋 9,879판에서 다섯 축의 상관을 재보니 최대 0.15 로 겹치지 않는다
# (교전·성장·오브젝트·공성·시야). 겹치는 축을 넣으면 같은 말을 두 번 그리는 셈이다.
#
# 값은 절대량이 아니라 **백분위**로 그린다. "교전 11" 은 아무 뜻도 없지만
# "상위 25%" 는 읽힌다. 기준선은 학습셋 분위수다(아래 RADAR_Q).
RADAR_AXES = ["교전", "라인", "정글", "오브젝트", "시야"]

# 축별 (25%, 50%, 75%, 95%) 분위수 — 학습셋 9,879판 실측.
# "공성"(타워)은 뺐다 — 10분 시점에는 91.8% 의 판이 0 이라 축이 되지 못한다.
# 대신 정글을 라인과 분리했다(상관 0.02). 다섯 축 최대 상관 0.13.
RADAR_Q = {
    "교전": (4.0, 6.0, 11.0, 19.0),
    "라인": (10.0, 20.0, 35.0, 61.0),
    "정글": (4.0, 9.0, 16.0, 28.0),
    "오브젝트": (1.0, 1.0, 2.0, 2.0),
    "시야": (3.0, 6.0, 21.0, 61.0),
}


def _axis_values(feats: dict) -> dict:
    return {
        "교전": abs(feats["KillsDiff"]) + abs(feats["AssistsDiff"]),
        "라인": abs(feats["TotalMinionsKilledDiff"]),
        "정글": abs(feats["TotalJungleMinionsKilledDiff"]),
        "오브젝트": abs(feats["DragonsDiff"]) + abs(feats["HeraldsDiff"]),
        "시야": abs(feats["WardsPlacedDiff"]) + abs(feats["WardsDestroyedDiff"]),
    }


def _percentile(axis: str, v: float) -> int:
    """분위수 사이를 선형 보간해 0~100 으로. 화면은 이 값만 쓴다."""
    q25, q50, q75, q95 = RADAR_Q[axis]
    pts = [(0.0, 0), (q25, 25), (q50, 50), (q75, 75), (q95, 95)]
    if v >= q95:
        return 100 if v > q95 else 95
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if v <= x1:
            if x1 == x0:
                return y1
            return int(round(y0 + (v - x0) / (x1 - x0) * (y1 - y0)))
    return 95


def radar_of(games: list) -> dict | None:
    """여러 판을 모아 다섯 축 백분위 — "당신은 어떤 유형인가".

    한 판으로는 성향이 아니다. 3판 이상일 때만 낸다.
    """
    rows = [g.get("features") for g in games if g.get("features")]
    if len(rows) < 3:
        return None
    sums = {a: 0.0 for a in RADAR_AXES}
    for f in rows:
        try:
            for a, v in _axis_values(f).items():
                sums[a] += v
        except KeyError:
            return None
    axes = [{"name": a, "score": _percentile(a, sums[a] / len(rows))} for a in RADAR_AXES]

    top = max(axes, key=lambda x: x["score"])
    low = min(axes, key=lambda x: x["score"])
    sc = {a["name"]: a["score"] for a in axes}
    spread = top["score"] - low["score"]

    # 유형 이름 — 1축만 보면 "싸움꾼" 아니면 "균형형" 둘뿐이라 심심하다.
    # 상위 두 축의 조합까지 보면 성격이 드러난다.
    second = sorted(axes, key=lambda x: -x["score"])[1]
    PAIR = {
        ("교전", "라인"): ("주도권형", "싸움도 걸고 CS 도 챙깁니다. 라인 주도권을 쥡니다"),
        ("교전", "정글"): ("갱킹형", "정글을 돌며 싸움을 만듭니다"),
        ("교전", "오브젝트"): ("한타 설계형", "싸움을 오브젝트로 연결합니다"),
        ("교전", "시야"): ("매복형", "시야를 잡고 기습을 노립니다"),
        ("라인", "정글"): ("수확형", "라인과 정글을 두루 먹어 성장합니다"),
        ("라인", "오브젝트"): ("운영형", "조용히 벌어 오브젝트로 굳힙니다"),
        ("라인", "시야"): ("안정형", "시야를 깔고 안전하게 파밍합니다"),
        ("정글", "오브젝트"): ("정글 운영형", "정글을 돌며 오브젝트를 선점합니다"),
        ("정글", "시야"): ("정찰형", "정글을 돌며 시야를 장악합니다"),
        ("오브젝트", "시야"): ("맵 장악형", "시야로 오브젝트를 선점합니다"),
    }
    SOLO = {
        "교전": ("싸움꾼", "교전이 잦습니다. 킬·어시스트로 격차를 만듭니다"),
        "라인": ("파머", "미니언으로 격차를 만듭니다. 싸움보다 라인전"),
        "정글": ("정글러형", "정글 몬스터를 많이 먹습니다"),
        "오브젝트": ("오브젝트형", "드래곤·전령을 챙겨 이득을 봅니다"),
        "시야": ("시야 장인", "와드로 맵을 밝히고 지웁니다"),
    }
    if spread < 30:
        label, desc = "균형형", "다섯 축이 고릅니다. 한쪽에 치우치지 않은 유형입니다"
    elif top["score"] >= 60 and second["score"] >= 55 and top["name"] != second["name"]:
        key = tuple(sorted([top["name"], second["name"]],
                           key=lambda n: RADAR_AXES.index(n)))
        label, desc = PAIR.get(key, SOLO[top["name"]])
    else:
        label, desc = SOLO[top["name"]]

    return {"axes": axes, "n": len(rows), "label": label, "desc": desc,
            "top_axis": top["name"], "top_score": top["score"],
            "strong": top["name"], "weak": low["name"],
            "note": f"{len(rows)}판 평균을 전체 경기와 견준 백분위입니다. "
                    f"높다고 잘하는 것이 아니라 그 쪽에 치우쳤다는 뜻입니다."}


# ── 경기 스타일 — "격차를 무엇이 만들었나" ────────────────────────
# 군집 실험에서 배운 것: 유형은 승패를 예측하지 못한다(같은 격차면 역전율 40% 로 동일).
# 그래서 예측에는 쓰지 않고, "어떻게 이겼나/졌나" 를 설명하는 데만 쓴다.
#
# 격차의 '크기' 는 빼고 '구성 비중' 만 본다. 크기를 넣으면 골드 격차를 되읽을 뿐이라
# 새 정보가 없다(골드가 벌어질수록 싸움도 많아진다 — 실측 4.3 → 17.1).
STYLE_NAME = {"fight": "싸움", "farm": "파밍", "objective": "오브젝트"}
STYLE_DESC = {
    "fight": "킬·어시스트가 격차를 만든 판입니다. 교전 결과가 그대로 점수가 됐습니다.",
    "farm": "미니언이 격차를 만든 판입니다. 싸움보다 라인전에서 벌었습니다.",
    "objective": "드래곤·전령·타워가 격차를 만든 판입니다. 오브젝트 운영이 컸습니다.",
}


def style_of(feats: dict) -> dict | None:
    """10분 격차를 무엇이 만들었나 — 비중으로 본다.

    반환: {"key","name","desc","shares":{...},"clear":bool}
    clear=False 면 한 가지로 부르기 애매한 판이다(1위 비중 50% 미만 · 전체의 29%).
    """
    try:
        fight = abs(feats["KillsDiff"]) + abs(feats["AssistsDiff"])
        farm = abs(feats["TotalMinionsKilledDiff"]) / 10
        obj = (abs(feats["DragonsDiff"]) + abs(feats["HeraldsDiff"])
               + abs(feats["TowersDestroyedDiff"])) * 3
    except KeyError:
        return None
    total = fight + farm + obj
    if total <= 0:
        return None
    shares = {"fight": fight / total, "farm": farm / total, "objective": obj / total}
    key = max(shares, key=shares.get)
    return {"key": key, "name": STYLE_NAME[key], "desc": STYLE_DESC[key],
            "shares": {k: round(v, 3) for k, v in shares.items()},
            "clear": shares[key] >= 0.5}


def style_summary(games: list) -> dict | None:
    """여러 판을 모아 성향과 유형별 승률 — "당신은 어떤 판에 강한가".

    한 판으로는 아무 말도 못 한다. 유형별로 3판 이상 쌓였을 때만 승률을 낸다.
    """
    from collections import defaultdict

    agg = defaultdict(lambda: {"n": 0, "won": 0})
    for g in games:
        st = g.get("style")
        if not st:
            continue
        a = agg[st["key"]]
        a["n"] += 1
        a["won"] += 1 if g.get("my_won") else 0
    if not agg:
        return None
    rows = [{"key": k, "name": STYLE_NAME[k], "games": v["n"], "wins": v["won"],
             "win_rate": round(v["won"] / v["n"], 4),
             "enough": v["n"] >= 3}
            for k, v in agg.items()]
    rows.sort(key=lambda r: -r["games"])
    judged = [r for r in rows if r["enough"]]
    note = None
    if len(judged) >= 2:
        best, worst = max(judged, key=lambda r: r["win_rate"]), min(judged, key=lambda r: r["win_rate"])
        if best["key"] != worst["key"] and best["win_rate"] - worst["win_rate"] >= 0.25:
            note = (f"{best['name']} 판에서 {best['win_rate']:.0%}, "
                    f"{worst['name']} 판에서 {worst['win_rate']:.0%} — "
                    f"{worst['name']} 쪽을 다시 볼 만합니다.")
    return {"rows": rows, "note": note,
            "caution": "판수가 적어 참고용입니다. 유형은 승패를 예측하지 않습니다 — "
                       "같은 골드 격차라면 어떤 유형이든 역전 확률은 비슷했습니다."}


def verdict_of(win_prob: float, won: bool) -> str:
    """10분 시점 유불리 x 실제 결과 = 네 갈래 판정.

    이 서비스의 존재 이유다. 다른 전적 사이트는 "무슨 일이 있었나"(KDA·CS)를 보여주지만,
    10분 시점 모델이 있어야 **언제 갈렸나**를 말할 수 있다.
    '역전패'는 10분에 유리했는데 진 경기라, 사용자가 가장 먼저 다시 볼 판이다.

    win_prob 는 **판단 주체 기준** 확률이다 — 소환사 조회면 그 사람 팀 기준,
    샘플 경기면 블루 기준. 판정 규칙 자체는 같으므로 여기 한 곳에만 둔다.
    """
    ahead = win_prob >= 0.5
    if ahead and won:
        return "우세승"
    if ahead and not won:
        return "역전패"
    if not ahead and won:
        return "역전승"
    return "열세패"


def _apply(features: dict, name: str, delta: float) -> dict:
    """지표 하나를 delta 만큼 올리고, 따라오는 골드도 함께 올린 상태를 만든다."""
    out = dict(features)
    out[name] = float(out.get(name, 0)) + delta
    if name != "GoldDiff":
        out["GoldDiff"] = float(out.get("GoldDiff", 0)) + GOLD_PER_UNIT.get(name, 0.0) * delta
    return out


def advise(features: dict, top_n: int = 3) -> dict:
    """이 경기 상태에서 무엇을 했다면 승률이 얼마나 올랐는지 계산한다.

    반환: {"win_prob": 현재, "actions": [{지표·할 일·예상 승률·상승폭}, ...]}
    actions 는 승률 상승이 큰 순서다.
    """
    missing = [f for f in DIFF13 if f not in features]
    if missing:
        raise ValueError(f"피처가 없습니다: {', '.join(missing)}")

    base = predict(features)["win_prob_blue"]
    actions = []
    for name, (step, label) in COACH_STEP.items():
        after = predict(_apply(features, name, step))["win_prob_blue"]
        actions.append({
            "feature": name,
            "name": KOREAN.get(name, name),
            "action": label,
            "win_prob_after": round(after, 4),
            "gain": round(after - base, 4),
        })
    actions.sort(key=lambda a: a["gain"], reverse=True)
    return {
        "win_prob": round(base, 4),
        "actions": actions[:top_n],
        # 화면 없이 API 만 쓰는 쪽도 같은 해석 선을 지키도록 응답에 함께 싣는다
        "how_to_read": ("관찰 데이터 기반 가정 계산입니다. 지표를 올릴 때 따라오는 골드도 "
                        "함께 올려 계산하며, 개입 효과(인과)의 증명이 아니라 "
                        "'그런 상태였던 경기들은 이만큼 이겼다'는 뜻입니다. 지표는 팀 단위입니다."),
    }


def verdict_advice(verdict: str) -> dict:
    """판정에 대한 처방 한 줄 + 설명."""
    head, body = VERDICT_ADVICE.get(verdict, ("", ""))
    return {"verdict": verdict, "headline": head, "detail": body}
