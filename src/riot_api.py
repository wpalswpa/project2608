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


LAST_APP_COUNT = [0]      # 마지막 응답의 120초 창 사용량 (배치가 참고한다)


class RiotApiError(RuntimeError):
    pass


class RateLimited(RiotApiError):
    """Riot 한도 초과. 몇 초 뒤에 다시 되는지(retry_after)를 담아 위로 올린다.

    웹 요청 안에서 기다리면 안 된다 — 스레드를 수십 초 붙잡고 결과는 어차피 실패라
    프록시 타임아웃(502)이 난다. 즉시 올려서 화면이 "N초 후 다시" 를 안내하게 한다.
    """

    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        super().__init__(f"Riot API 요청이 잠시 많습니다. {self.retry_after}초 후 다시 시도해 주세요.")


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
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            # 배치 수집기가 "라이브에 얼마나 남았나" 를 보고 스스로 물러나려면
            # 이 값이 필요하다. 헤더 형식: "12:120,1:1" (120초 창의 사용량이 앞)
            hdr = r.headers.get("X-App-Rate-Limit-Count") or ""
            try:
                LAST_APP_COUNT[0] = int(hdr.split(":")[0])
            except (ValueError, IndexError):
                pass
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            code, retry_after = e.code, e.headers.get("Retry-After", "10")
        finally:
            e.close()           # 닫지 않으면 소켓이 GC 될 때까지 남는다
        if code == 429:
            # 여기서 기다리지 않는다 (위 RateLimited 설명 참고)
            raise RateLimited(retry_after) from None
        if code in (401, 403):
            raise RiotApiError("API 키가 만료됐거나 잘못됐습니다. "
                               "developer.riotgames.com 에서 REGENERATE 후 다시 설정하세요.") from None
        if code == 404:
            raise RiotApiError("찾을 수 없습니다 (소환사명/태그 확인).") from None
        raise RiotApiError(f"Riot API 오류 HTTP {code}") from None


def get_with_wait(url: str, tries: int = 5) -> dict:
    """한도에 걸리면 기다렸다 재시도한다 — **배치 수집 전용**.

    웹 요청 경로에서는 쓰지 않는다. 사용자를 기다리게 하면 안 되기 때문이다.
    """
    for _ in range(tries):
        try:
            return _get(url)
        except RateLimited as e:
            time.sleep(min(e.retry_after, 30))
    raise RiotApiError("요청 한도가 계속 걸립니다. 잠시 후 다시 실행하세요.")


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
    except urllib.error.HTTPError as e:
        code = e.code
        e.close()
        # 429 는 키가 죽은 게 아니라 잠깐 붐비는 것이다. 여기서 False 를 주면
        # 사이트가 "소환사 검색 중단 + 입력 비활성" 으로 굳어 다음 재시작까지 안 풀린다.
        # 키가 진짜 잘못된 경우(401/403)만 False 로 본다.
        return code == 429
    except Exception:
        return False


def get_puuid(game_name: str, tag_line: str) -> str:
    g = urllib.parse.quote(game_name)
    t = urllib.parse.quote(tag_line)
    acc = _get(f"https://{ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{g}/{t}")
    return acc["puuid"]


def get_recent_match_ids(puuid: str, count: int = 5, start: int = 0) -> list:
    """최근 솔로랭크 경기 id 목록. start 는 건너뛸 개수 — "더 보기" 에 쓴다."""
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/"
                f"by-puuid/{puuid}/ids?queue={SOLO_QUEUE}&count={count}&start={start}")


def get_match(match_id: str) -> dict:
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}")


def get_timeline(match_id: str) -> dict:
    return _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")


def timeline_trajectory(timeline: dict, blue_ids: set, upto: int = 15) -> list:
    """분 단위 골드 격차 궤적 — "몇 분에 갈렸나" 를 말하기 위한 데이터.

    타임라인은 분마다 프레임을 주는데 우리는 10분 한 장만 쓰고 나머지를 버려 왔다.
    추가 API 호출 없이 이미 받은 응답에서 뽑는다.

    반환: [{"minute": 0, "gold_diff": 0}, ...]  (블루 − 레드)
    """
    out = []
    for i, fr in enumerate(timeline["info"]["frames"]):
        if i > upto:
            break
        b = r = 0
        for pid, pf in fr["participantFrames"].items():
            if int(pid) in blue_ids:
                b += pf["totalGold"]
            else:
                r += pf["totalGold"]
        out.append({"minute": i, "gold_diff": b - r})
    return out


def swing_minute(traj: list, threshold: int = 1000) -> int | None:
    """격차가 벌어지기 시작해 **다시 안 좁혀진** 분 — "이 판은 N분에 갈렸다" 의 N.

    기준은 EDA 의 접전 경계(골드차 1,000)를 그대로 쓴다.
    단순히 "처음 1,000을 넘은 분" 을 잡으면 안 된다 — 3분에 잠깐 벌어졌다가
    다시 붙는 판이 많아서, 그걸 "3분에 갈렸다" 고 말하면 틀린다.
    그래서 **마지막으로 접전이었던 분의 다음** 을 잡는다. 그 뒤로는 안 좁혀졌다는 뜻이다.

    끝까지 접전이었으면 None — "아직 안 갈렸다" 가 맞는 답이다.
    """
    if not traj:
        return None
    last_close = None
    for p in traj:
        if abs(p["gold_diff"]) < threshold:
            last_close = p["minute"]
    if last_close is None:
        return traj[0]["minute"]                        # 처음부터 벌어져 있었다
    if last_close == traj[-1]["minute"]:
        return None                                     # 마지막까지 접전 — 안 갈렸다
    return last_close + 1


def lane_matchup(timeline: dict, participants: list, my_puuid: str) -> dict | None:
    """같은 포지션 상대와 나의 10분 시점 비교 — "팀이" 가 아니라 "당신이" 를 말하려면 필요하다.

    팀 합계만 보면 "우리 팀이 밀렸다" 까지만 나온다. 같은 라인 상대와 견주면
    내 몫이 얼마였는지가 보인다. 이미 받은 타임라인·매치 응답에서 뽑으므로
    추가 API 호출이 없다.
    """
    me = next((p for p in participants if p["puuid"] == my_puuid), None)
    if not me or not me.get("teamPosition"):
        return None
    opp = next((p for p in participants
                if p.get("teamPosition") == me["teamPosition"]
                and p["teamId"] != me["teamId"]), None)
    if not opp:
        return None

    frames = timeline["info"]["frames"]
    if len(frames) <= 10:
        return None
    pf = frames[10]["participantFrames"]
    mine = pf.get(str(me["participantId"]))
    theirs = pf.get(str(opp["participantId"]))
    if not mine or not theirs:
        return None

    def cs(x):
        return x["minionsKilled"] + x["jungleMinionsKilled"]

    return {
        "position": me["teamPosition"],
        "me": {"champion": me.get("championName"), "cs": cs(mine),
               "gold": mine["totalGold"], "level": mine["level"]},
        "opponent": {"champion": opp.get("championName"), "cs": cs(theirs),
                     "gold": theirs["totalGold"], "level": theirs["level"]},
        "cs_diff": cs(mine) - cs(theirs),
        "gold_diff": mine["totalGold"] - theirs["totalGold"],
        "level_diff": mine["level"] - theirs["level"],
    }


def first_objectives(timeline: dict, blue_ids: set) -> dict:
    """첫 드래곤·전령·타워를 몇 분에 누가 가져갔나 (0~10분).

    "첫 드래곤을 평균 몇 분에 가져가나" 같은 이야기를 하려면 시각이 필요하다.
    이벤트는 이미 받고 있는데 개수만 세고 시각을 버리고 있었다.
    """
    out = {}
    for fr in timeline["info"]["frames"][:11]:
        for e in fr.get("events", []):
            ts = e.get("timestamp", 0)
            if ts >= TEN_MIN_MS:
                continue
            kind = None
            if e["type"] == "ELITE_MONSTER_KILL":
                m = e.get("monsterType", "")
                kind = "dragon" if m == "DRAGON" else ("herald" if m == "RIFTHERALD" else None)
                side = "블루" if e.get("killerTeamId") == 100 else "레드"
            elif e["type"] == "BUILDING_KILL" and e.get("buildingType") == "TOWER_BUILDING":
                kind = "tower"
                side = "레드" if e.get("teamId") == 100 else "블루"   # 부서진 쪽의 반대
            if kind and kind not in out:
                out[kind] = {"minute": round(ts / 60000, 1), "side": side}
    return out


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


PLATFORM = "kr"           # 랭크 정보는 대륙(asia)이 아니라 플랫폼(kr) 라우팅


_RANK_CACHE: dict = {}          # puuid -> rank | None. 같은 사람이 여러 판에 나오므로 한 번만 조회한다


def get_rank(puuid: str) -> dict | None:
    """솔로랭크 티어. 실패해도 예외를 올리지 않는다 — 부가 정보라 조회가 막혀도 본 기능은 살아야 한다."""
    if puuid in _RANK_CACHE:
        return _RANK_CACHE[puuid]
    try:
        got = None
        for e in _get(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"):
            if e.get("queueType") == "RANKED_SOLO_5x5":
                got = {"tier": e["tier"], "rank": e["rank"], "lp": e["leaguePoints"],
                       "wins": e["wins"], "losses": e["losses"]}
                break
        # 성공했을 때만 캐시한다. 한도 초과(429)로 못 받은 것을 "언랭" 으로 굳혀 버리면
        # 서버를 재시작할 때까지 그 사람 티어가 영영 안 나온다 — 실제로 그렇게 됐다.
        _RANK_CACHE[puuid] = got
        return got
    except RateLimited:
        return None                 # 캐시하지 않는다 — 다음 요청에서 다시 시도
    except Exception:
        _RANK_CACHE[puuid] = None   # 언랭 등 진짜 없는 경우만 굳힌다
        return None


def analyze_recent(riot_id: str, count: int = 5, start: int = 0, with_ranks: bool = False) -> dict:
    """소환사의 최근 솔로랭크 경기들을 10분 시점에서 복기한다.

    riot_id: "게임명#태그" (예: "Hide on bush#KR1")
    반환: {"riot_id": ..., "games": [경기별 {예측, 실제, 피처, 정보}]}
    """
    from lolwin.coach import verdict_of           # 판정 정본 (샘플 경기와 공유)
    from lolwin.features import gold_bin_bounds   # 구간 경계 정본
    from predict import predict          # 예측은 단일 진실만 사용

    if "#" not in riot_id:
        raise RiotApiError('Riot ID는 "게임명#태그" 형식입니다 (예: Hide on bush#KR1)')
    name, tag = riot_id.rsplit("#", 1)
    puuid = get_puuid(name.strip(), tag.strip())
    games = []
    for mid in get_recent_match_ids(puuid, count, start):
        m = get_match(mid)
        info = m["info"]
        if info.get("gameDuration", 0) < 660:        # 11분 미만(조기 항복 등) 제외
            continue
        blue_ids = {p["participantId"] for p in info["participants"] if p["teamId"] == 100}
        red_ids = {p["participantId"] for p in info["participants"] if p["teamId"] == 200}
        me = next(p for p in info["participants"] if p["puuid"] == puuid)
        tl = get_timeline(mid)
        feats = timeline_to_diff13(tl, blue_ids, red_ids)
        traj = timeline_trajectory(tl, blue_ids)
        lane = lane_matchup(tl, info["participants"], puuid)
        firsts = first_objectives(tl, blue_ids)
        pred = predict(feats)
        blue_won = next(t["win"] for t in info["teams"] if t["teamId"] == 100)
        # 내가 레드면 확률·승패를 내 팀 기준으로 뒤집는다 (사용자는 자기 팀 기준으로 읽는다)
        i_am_blue = me["teamId"] == 100
        my_p = pred["win_prob_blue"] if i_am_blue else 1 - pred["win_prob_blue"]
        my_won = bool(blue_won) if i_am_blue else not blue_won
        # 경기 날짜 — "언제 범위의 전적인가" 를 화면이 한 줄로 보여주기 위해
        played_at = time.strftime("%m.%d", time.localtime(info.get("gameCreation", 0) / 1000))
        # 팀원·상대 정보는 이미 받은 match 응답에 들어 있다 (추가 호출 0회).
        # 펼쳤을 때 "누구와 함께였고 누구를 상대했나" 를 보여주기 위해 정리해 둔다.
        roster = [{
            "name": (p.get("riotIdGameName") or "").strip(),
            "tag": p.get("riotIdTagline") or "",
            "champion": p.get("championName"),
            "position": p.get("teamPosition") or "",
            "kda": f"{p.get('kills', 0)}/{p.get('deaths', 0)}/{p.get('assists', 0)}",
            "side": "블루" if p["teamId"] == 100 else "레드",
            "is_me": p["puuid"] == puuid,
            "puuid": p["puuid"],
            # 참가자 10명 티어는 판마다 최대 10콜이라 기본 응답에서는 뺀다.
            # 행을 펼칠 때 /api/ranks 로 따로 받는다 (첫 페이지 비용 22 → 12).
            "rank": get_rank(p["puuid"]) if with_ranks else None,
        } for p in info["participants"]]

        games.append({
            "match_id": mid,
            "played_at": played_at,
            "roster": roster,
            "champion": me["championName"],
            "my_side": "블루" if me["teamId"] == 100 else "레드",
            "duration_min": round(info["gameDuration"] / 60),
            "game_version": ".".join(info.get("gameVersion", "").split(".")[:2]),
            "features": feats,
            # 분 단위 궤적 — 이미 받은 타임라인에서 뽑는다 (추가 호출 0회)
            "trajectory": traj,
            "swing_minute": swing_minute(traj),
            "lane": lane,                  # 같은 라인 상대와의 10분 비교 (개인화)
            "first_objectives": firsts,    # 첫 드래곤·전령·타워 시각
            "win_prob_blue": pred["win_prob_blue"],
            "pred_label": pred["pred_label"],
            "top_factors": pred["top_factors"],
            "warnings": pred["warnings"],
            "actual": "블루 승리" if blue_won else "레드 승리",
            "model_correct": (pred["pred"] == 1) == blue_won,
            # 아래 넷은 화면이 계산하지 않도록 서버가 준다 (계산 정본은 한 곳만)
            "band": next((lab for lab, hi in gold_bin_bounds()
                          if abs(feats["GoldDiff"]) < hi), gold_bin_bounds()[-1][0]),
            "my_win_prob": round(my_p, 4),
            "my_won": my_won,
            "verdict": verdict_of(my_p, my_won),
        })
    # 첫 화면 요약 타일이 쓸 값 — 화면에서 세지 않게 서버가 센다
    from collections import Counter
    counts = Counter(g["verdict"] for g in games)
    summary = {
        "n": len(games),
        # 조회 범위 (가장 오래된 판 ~ 최신 판)
        "period": (f"{games[-1]['played_at']} ~ {games[0]['played_at']}" if games else None),
        "avg_win_prob_10min": round(sum(g["my_win_prob"] for g in games) / len(games), 4) if games else None,
        "역전패": counts.get("역전패", 0),
        "열세패": counts.get("열세패", 0),
        "역전승": counts.get("역전승", 0),
        "우세승": counts.get("우세승", 0),
        "model_correct": sum(1 for g in games if g["model_correct"]),
    }
    return {"riot_id": riot_id, "queue": "솔로랭크", "rank": get_rank(puuid),
            "games": games, "summary": summary,
            "start": start, "next_start": start + count}


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
