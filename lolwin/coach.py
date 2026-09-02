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
    "역전패": ("이긴 판을 닫지 못하고 있습니다.",
               "10분에 앞서고도 졌습니다. 리드를 굴리는 법이 문제입니다 — "
               "앞설 때 오브젝트로 바꾸고, 무리한 교전으로 격차를 되돌려주지 마세요."),
    "초반 붕괴": ("라인전에서 이미 지고 시작합니다.",
                  "10분에 밀린 채로 그대로 졌습니다. 후반 운영보다 "
                  "**10분까지 버티는 것**이 먼저입니다."),
    "역전승": ("불리해도 살아나는 힘이 있습니다.",
               "10분에 밀렸는데 이겼습니다. 후반 집중력은 강점이니, "
               "초반 손해만 줄이면 훨씬 편해집니다."),
    "굴렸다": ("앞서서 시작해 그대로 이겼습니다.",
               "가장 이상적인 형태입니다. 이 판의 초반을 표준으로 삼으세요."),
}


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
    return {"win_prob": round(base, 4), "actions": actions[:top_n]}


def verdict_advice(verdict: str) -> dict:
    """판정에 대한 처방 한 줄 + 설명."""
    head, body = VERDICT_ADVICE.get(verdict, ("", ""))
    return {"verdict": verdict, "headline": head, "detail": body}
