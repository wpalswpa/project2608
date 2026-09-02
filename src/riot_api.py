# Riot API 연동 — 소환사의 "끝난 경기"를 불러와 10분 시점 피처로 바꾼다
#
# 사용 (명령행):
#   $env:RIOT_API_KEY='RGAPI-...'            # 키는 환경변수로만! 코드에 넣지 말 것
#   python src/riot_api.py "Hide on bush#KR1"
#
# 사용 (함수):
#   from riot_api import analyze_recent      # 웹(web/app.py)이 이걸 쓴다
#
# 할 수 있는 것: 끝난 경기의 10분 시점 승률 복기 (Match-V5 타임라인)
# 할 수 없는 것: 진행 중 경기의 실시간 승률 — 라이엇이 실시간 수치를 API로 주지 않음
#
# 예측은 여기서 하지 않는다. 이 모듈은 "타임라인 → 13개 차이 피처" 변환만 하고,
# 예측은 언제나 predict.py 가 한다 (예측 로직의 단일 진실).
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import cd_root

_root = cd_root()
sys.path.insert(0, str(_root))   # 루트의 predict.py 를 import 하기 위해

ROUTING = "asia"          # 한국 계정/매치는 asia 대륙 라우팅
TEN_MIN_MS = 600_000      # 10분 = 600,000ms — 학습 데이터(10분 스냅샷)와 같은 기준
SOLO_QUEUE = 420          # 솔로랭크 — 학습 데이터와 같은 큐만 기본 분석


class RiotApiError(RuntimeError):
    pass


def _get(url: str) -> dict:
    """API 호출. 키는 환경변수 RIOT_API_KEY 에서만 읽는다."""
    key = os.environ.get("RIOT_API_KEY")
    if not key:
        raise RiotApiError("RIOT_API_KEY 환경변수가 없습니다. "
                           "developer.riotgames.com 에서 키를 받아 설정하세요.")
    # User-Agent 필수: 없으면 Cloudflare가 파이썬 기본 UA를 차단한다 (error 1010 → HTTP 403)
    req = urllib.request.Request(url, headers={
        "X-Riot-Token": key,
        "User-Agent": "Mozilla/5.0 (team-project; LoL win-prediction; educational)",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:                       # 요청 한도 초과 → 잠시 기다렸다 재시도
                wait = int(e.headers.get("Retry-After", "2"))
                time.sleep(min(wait, 10))
                continue
            if e.code in (401, 403):
                raise RiotApiError("API 키가 만료됐거나 잘못됐습니다. "
                                   "developer.riotgames.com 에서 REGENERATE 후 다시 설정하세요.") from e
            if e.code == 404:
                raise RiotApiError("찾을 수 없습니다 (소환사명/태그 확인).") from e
            raise RiotApiError(f"Riot API 오류 HTTP {e.code}") from e
    raise RiotApiError("요청 한도 초과가 계속됩니다. 잠시 후 다시 시도하세요.")


def key_works(timeout: int = 6) -> bool:
    """지금 설정된 키가 실제로 통하는가 — 키가 있는지가 아니라 살아있는지 본다.

    개발용 키는 24시간마다 죽는다. 키가 '있다'는 것만 보고 화면에서 소환사 검색을
    권하면, 죽은 키일 때 사용자가 검색하고 나서야 실패를 본다. 발표 시연에서
    서비스가 고장 난 것처럼 보이므로, 서버 기동 때 한 번 확인해 둔다.

    실패해도 예외를 올리지 않는다 — 이 확인 때문에 서버가 못 뜨면 안 된다.
    """
    key = os.environ.get("RIOT_API_KEY")
    if not key:
        return False
    try:
        # 가장 가벼운 호출: 서버 상태 조회 (계정 조회와 달리 대상이 필요 없다)
        req = urllib.request.Request(
            "https://kr.api.riotgames.com/lol/status/v4/platform-data",
            headers={"X-Riot-Token": key,
                     "User-Agent": "Mozilla/5.0 (team-project; LoL win-prediction; educational)"})
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


def get_puuid(game_name: str, tag_line: str) -> str:
    g = urllib.parse.quote(game_name)
    t = urllib.parse.quote(tag_line)
    acc = _get(f"https://{ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{g}/{t}")
    return acc["puuid"]


def get_recent_match_ids(puuid: str, count: int = 5) -> list:
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/"
                f"by-puuid/{puuid}/ids?queue={SOLO_QUEUE}&count={count}")


def get_match(match_id: str) -> dict:
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}")


def get_timeline(match_id: str) -> dict:
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")


def timeline_to_diff13(timeline: dict, blue_ids: set, red_ids: set) -> dict:
    """타임라인 → 13개 차이 피처 (블루−레드). 학습 데이터(Kaggle 10분 스냅샷)와 같은 정의.

    blue_ids/red_ids: 팀별 participantId 집합 (매치 상세에서 만들어 넘긴다)
    """
    frames = timeline["info"]["frames"]
    if len(frames) <= 10:
        raise RiotApiError("10분 전에 끝난 경기입니다 (분석 불가).")

    # ---- 10분 시점 상태 (frames[10].participantFrames) ----
    sums = {"blue": dict(gold=0, xp=0, cs=0, jg=0, lvl=0),
            "red": dict(gold=0, xp=0, cs=0, jg=0, lvl=0)}
    for pid_str, pf in frames[10]["participantFrames"].items():
        side = "blue" if int(pid_str) in blue_ids else "red"
        s = sums[side]
        s["gold"] += pf["totalGold"]
        s["xp"] += pf["xp"]
        s["cs"] += pf["minionsKilled"]
        s["jg"] += pf["jungleMinionsKilled"]
        s["lvl"] += pf["level"]
    b, r = sums["blue"], sums["red"]

    # ---- 0~10분 이벤트 집계 ----
    cnt = {k: {"blue": 0, "red": 0} for k in
           ("kills", "assists", "wards_placed", "wards_killed",
            "dragons", "heralds", "towers")}
    first_blood_blue = 0
    seen_first_kill = False
    for fr in frames[:11]:
        for e in fr["events"]:
            if e.get("timestamp", 0) >= TEN_MIN_MS:
                continue
            t = e["type"]
            if t == "CHAMPION_KILL":
                killer = e.get("killerId", 0)
                if killer in blue_ids or killer in red_ids:
                    side = "blue" if killer in blue_ids else "red"
                    cnt["kills"][side] += 1
                    if not seen_first_kill:              # 첫 킬 = 퍼스트 블러드
                        seen_first_kill = True
                        first_blood_blue = 1 if side == "blue" else 0
                    for a in e.get("assistingParticipantIds", []):
                        cnt["assists"]["blue" if a in blue_ids else "red"] += 1
            elif t == "WARD_PLACED":
                c = e.get("creatorId", 0)
                if c in blue_ids or c in red_ids:
                    cnt["wards_placed"]["blue" if c in blue_ids else "red"] += 1
            elif t == "WARD_KILL":
                k = e.get("killerId", 0)
                if k in blue_ids or k in red_ids:
                    cnt["wards_killed"]["blue" if k in blue_ids else "red"] += 1
            elif t == "ELITE_MONSTER_KILL":
                side = "blue" if e.get("killerTeamId") == 100 else "red"
                m = e.get("monsterType", "")
                if m == "DRAGON":
                    cnt["dragons"][side] += 1
                elif m == "RIFTHERALD":
                    cnt["heralds"][side] += 1
            elif t == "BUILDING_KILL" and e.get("buildingType") == "TOWER_BUILDING":
                # teamId = "부서진" 건물의 소유 팀 → 부순 쪽은 반대 팀
                destroyer = "red" if e.get("teamId") == 100 else "blue"
                cnt["towers"][destroyer] += 1

    return {
        "FirstBlood": first_blood_blue,
        "KillsDiff": cnt["kills"]["blue"] - cnt["kills"]["red"],
        "GoldDiff": b["gold"] - r["gold"],
        "ExpDiff": b["xp"] - r["xp"],
        "WardsPlacedDiff": cnt["wards_placed"]["blue"] - cnt["wards_placed"]["red"],
        "WardsDestroyedDiff": cnt["wards_killed"]["blue"] - cnt["wards_killed"]["red"],
        "AssistsDiff": cnt["assists"]["blue"] - cnt["assists"]["red"],
        "DragonsDiff": cnt["dragons"]["blue"] - cnt["dragons"]["red"],
        "HeraldsDiff": cnt["heralds"]["blue"] - cnt["heralds"]["red"],
        "TowersDestroyedDiff": cnt["towers"]["blue"] - cnt["towers"]["red"],
        "AvgLevelDiff": b["lvl"] / 5 - r["lvl"] / 5,
        "TotalMinionsKilledDiff": b["cs"] - r["cs"],
        "TotalJungleMinionsKilledDiff": b["jg"] - r["jg"],
    }


def analyze_recent(riot_id: str, count: int = 5) -> dict:
    """소환사의 최근 솔로랭크 경기들을 10분 시점에서 복기한다.

    riot_id: "게임명#태그" (예: "Hide on bush#KR1")
    반환: {"riot_id": ..., "games": [경기별 {예측, 실제, 피처, 정보}]}
    """
    from predict import predict          # 예측은 단일 진실만 사용

    if "#" not in riot_id:
        raise RiotApiError('Riot ID는 "게임명#태그" 형식입니다 (예: Hide on bush#KR1)')
    name, tag = riot_id.rsplit("#", 1)
    puuid = get_puuid(name.strip(), tag.strip())
    games = []
    for mid in get_recent_match_ids(puuid, count):
        m = get_match(mid)
        info = m["info"]
        if info.get("gameDuration", 0) < 660:        # 11분 미만(조기 항복 등) 제외
            continue
        blue_ids = {p["participantId"] for p in info["participants"] if p["teamId"] == 100}
        red_ids = {p["participantId"] for p in info["participants"] if p["teamId"] == 200}
        me = next(p for p in info["participants"] if p["puuid"] == puuid)
        feats = timeline_to_diff13(get_timeline(mid), blue_ids, red_ids)
        pred = predict(feats)
        blue_won = next(t["win"] for t in info["teams"] if t["teamId"] == 100)
        games.append({
            "match_id": mid,
            "champion": me["championName"],
            "my_side": "블루" if me["teamId"] == 100 else "레드",
            "duration_min": round(info["gameDuration"] / 60),
            "game_version": ".".join(info.get("gameVersion", "").split(".")[:2]),
            "features": feats,
            "win_prob_blue": pred["win_prob_blue"],
            "pred_label": pred["pred_label"],
            "top_factors": pred["top_factors"][:3],
            "warnings": pred["warnings"],
            "actual": "블루 승리" if blue_won else "레드 승리",
            "model_correct": (pred["pred"] == 1) == blue_won,
        })
    return {"riot_id": riot_id, "queue": "솔로랭크", "games": games}


def _selftest():
    """API 없이 변환 로직만 검증 — 합성 타임라인으로 손계산과 비교한다."""
    blue_ids, red_ids = {1, 2, 3, 4, 5}, {6, 7, 8, 9, 10}
    pf = {}
    for i in range(1, 11):
        blue = i <= 5
        pf[str(i)] = dict(totalGold=3000 + (200 if blue else 0),
                          xp=4000 + (100 if blue else 0),
                          minionsKilled=50 + (2 if blue else 0),
                          jungleMinionsKilled=10, level=7 if blue else 6)
    events = [
        dict(type="CHAMPION_KILL", timestamp=100_000, killerId=6,
             assistingParticipantIds=[7]),                      # 레드 첫킬(+어시1)
        dict(type="CHAMPION_KILL", timestamp=200_000, killerId=1,
             assistingParticipantIds=[2, 3]),                   # 블루 킬(+어시2)
        dict(type="CHAMPION_KILL", timestamp=650_000, killerId=1),  # 10분 이후 → 제외
        dict(type="WARD_PLACED", timestamp=50_000, creatorId=5),
        dict(type="WARD_PLACED", timestamp=60_000, creatorId=9),
        dict(type="WARD_KILL", timestamp=70_000, killerId=2),
        dict(type="ELITE_MONSTER_KILL", timestamp=300_000,
             killerTeamId=100, monsterType="DRAGON"),
        dict(type="ELITE_MONSTER_KILL", timestamp=400_000,
             killerTeamId=200, monsterType="RIFTHERALD"),
        dict(type="BUILDING_KILL", timestamp=500_000,
             buildingType="TOWER_BUILDING", teamId=200),        # 레드 타워 파괴 → 블루가 부숨
    ]
    frames = [dict(participantFrames=pf, events=[]) for _ in range(11)]
    frames[10]["events"] = events
    tl = {"info": {"frames": frames}}
    f = timeline_to_diff13(tl, blue_ids, red_ids)
    expected = dict(FirstBlood=0, KillsDiff=0, GoldDiff=1000, ExpDiff=500,
                    WardsPlacedDiff=0, WardsDestroyedDiff=1, AssistsDiff=1,
                    DragonsDiff=1, HeraldsDiff=-1, TowersDestroyedDiff=1,
                    AvgLevelDiff=1.0, TotalMinionsKilledDiff=10,
                    TotalJungleMinionsKilledDiff=0)
    for k, v in expected.items():
        assert f[k] == v, f"{k}: 기대 {v}, 실제 {f[k]}"
    print("셀프테스트 통과 — 합성 타임라인 13개 피처 전부 손계산과 일치")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
    elif len(sys.argv) > 1:
        result = analyze_recent(sys.argv[1], count=5)
        print(f"\n=== {result['riot_id']} 최근 {result['queue']} ===")
        for g in result["games"]:
            mark = "적중" if g["model_correct"] else "빗나감"
            print(f"\n[{g['champion']} · {g['my_side']}팀 · {g['duration_min']}분 · 패치 {g['game_version']}]")
            print(f"  10분 시점 블루 승률 {g['win_prob_blue']:.1%} → {g['pred_label']}"
                  f" | 실제: {g['actual']} ({mark})")
            for tf in g["top_factors"]:
                print(f"  · {tf['name']} = {tf['value']:+g} ({tf['direction']})")
    else:
        print('사용법: python src/riot_api.py "게임명#태그"  또는  --selftest')
