# 챔피언·라인별 승률 수집 — 다이아 이상 솔로랭크
#
# 실행: python src/collect_champion_stats.py [--minutes 30] [--tier MASTER]
#
# 왜 이어받기(resumable)가 필수인가:
#   수집은 수천 건의 API 호출이라 중간에 끊길 수 있다(네트워크·한도·중단).
#   그래서 받은 경기를 즉시 파일에 한 줄씩 붙이고(JSONL), 다시 실행하면
#   이미 받은 match_id 를 건너뛴다. 몇 번에 나눠 돌려도 결과가 같다.
#
# 무엇을 모으나:
#   경기 하나당 참가자 10명 → (챔피언, 라인, 승패, 날짜, 공개 Riot ID) 10건.
#   puuid 같은 내부 식별자는 저장하지 않는다. 이름을 담는 이유는 화면에
#   "이 챔피언으로 승률이 높았던 유저" 를 공부용 참고로 보여주기 위해서다.
#
# 산출물:
#   data/champion_raw.jsonl              수집 원본 (.gitignore — 크고 재생성 가능)
#   reports/tables/champion_stats.csv        챔피언 x 라인 승률 (커밋)
#   reports/tables/champion_top_players.csv  챔피언별 상위 유저 (커밋)
import argparse
import json
import os
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

# .env 를 직접 읽는다 — 서버는 check_project.sh 가 넣어주지만 이 스크립트는 혼자 돈다
if not os.environ.get("RIOT_API_KEY") and os.path.exists(".env"):
    for _line in open(".env", encoding="utf-8"):
        if _line.strip().startswith("RIOT_API_KEY="):
            os.environ["RIOT_API_KEY"] = _line.split("=", 1)[1].strip()

from riot_api import (PLATFORM, ROUTING, SOLO_QUEUE,  # noqa: E402
                      LAST_APP_COUNT, RateLimited, RiotApiError, _get)

# 라이브 서비스와 **같은 API 키 예산**(100회/120초)을 나눠 쓴다.
# 페이싱 없이 몰아치면 예산을 몇 초에 태우고, 그동안 사용자 검색이 전부 실패한다.
# 0.8 req/s = 96회/120초로 예산 안에서 최대한 받는다.
PACE_SEC = 1.25
# 라이브 사용자를 위해 예산을 남겨둔다. 수집이 예산을 다 쓰면 서버는 안 죽지만
# 사용자의 소환사 조회(콜드 12콜)가 대부분 429 로 막힌다 — 실제로 그랬다.
# 카운터가 이 선을 넘으면 수집이 스스로 쉰다.
RESERVE = 70             # 120초 예산 100 중 30만 쓰고 나머지는 사용자 몫
_last_call = [0.0]


def _budget_wait():
    """라이브 예산이 얼마 안 남았으면 쉰다. 헤더를 못 읽으면 그냥 진행한다."""
    used = LAST_APP_COUNT[0]
    if used >= RESERVE:
        wait = 20
        print(f"  [양보] 라이브 예산 {used}/100 — {wait}초 쉽니다")
        time.sleep(wait)



def get_paced(url: str, tries: int = 4) -> dict:
    """수집 전용 호출 — 간격을 지키고, 한도에 걸리면 Retry-After 만큼 온전히 기다린다.

    웹 요청은 기다리면 안 되지만(502), 배치는 기다리는 것이 맞다.
    10초만 자고 건너뛰면 Riot 이 요구한 69초를 안 지켜 세 번 다 실패한다.
    """
    for _ in range(tries):
        gap = PACE_SEC - (time.time() - _last_call[0])
        if gap > 0:
            time.sleep(gap)
        _last_call[0] = time.time()
        try:
            r = _get(url)
            _budget_wait()
            return r
        except RateLimited as e:
            print(f"  [대기] 한도 초과 — {e.retry_after}초 쉽니다")
            time.sleep(e.retry_after + 1)
    raise RiotApiError("한도가 계속 걸립니다. 나중에 다시 실행하세요.")

RAW = "data/champion_raw.jsonl"
OUT = "reports/tables/champion_stats.csv"
MIN_DURATION = 660          # 11분 미만(조기 항복)은 제외 — 라인전 통계가 왜곡된다
TIERS = ("challengerleagues", "grandmasterleagues", "masterleagues")


def load_seen() -> set:
    """이미 받은 match_id — 이어받기의 핵심."""
    seen = set()
    if os.path.exists(RAW):
        with open(RAW, encoding="utf-8") as f:
            for line in f:
                try:
                    seen.add(json.loads(line)["match_id"])
                except Exception:
                    continue
    return seen


def puuids_from_apex(limit: int) -> list:
    """마스터 이상 계정의 puuid. 상위 티어일수록 메타가 정제돼 있어 기준으로 삼는다."""
    out = []
    for t in TIERS:
        try:
            entries = get_paced(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/{t}"
                                f"/by-queue/RANKED_SOLO_5x5")["entries"]
        except RiotApiError:
            continue
        out += [e["puuid"] for e in entries if e.get("puuid")]
        if len(out) >= limit:
            break
    return out[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20, help="이 시간만큼만 수집하고 종료")
    ap.add_argument("--players", type=int, default=400, help="표본으로 쓸 계정 수")
    ap.add_argument("--per-player", type=int, default=15, help="계정당 최근 경기 수")
    args = ap.parse_args()

    os.makedirs("data", exist_ok=True)
    os.makedirs("reports/tables", exist_ok=True)
    seen = load_seen()
    print(f"[시작] 이미 받은 경기 {len(seen):,}건 — 건너뜁니다")

    deadline = time.time() + args.minutes * 60
    players = puuids_from_apex(args.players)
    print(f"[표본] 마스터 이상 계정 {len(players):,}명")

    added = 0
    with open(RAW, "a", encoding="utf-8") as f:
        for i, pu in enumerate(players, 1):
            if time.time() > deadline:
                print("[중단] 시간 종료 — 다시 실행하면 이어서 받습니다")
                break
            try:
                ids = get_paced(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/"
                                f"by-puuid/{pu}/ids?queue={SOLO_QUEUE}&count={args.per_player}")
            except RiotApiError:
                continue

            for mid in ids:
                if mid in seen or time.time() > deadline:
                    continue
                try:
                    info = get_paced(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")["info"]
                except RiotApiError:
                    continue
                seen.add(mid)
                if info.get("gameDuration", 0) < MIN_DURATION:
                    continue
                patch = ".".join((info.get("gameVersion") or "").split(".")[:2])
                day = time.strftime("%Y-%m-%d", time.localtime(info.get("gameCreation", 0) / 1000))
                for p in info["participants"]:
                    # 공개 Riot ID 만 담는다 (puuid 같은 내부 식별자는 저장하지 않는다).
                    # "이 챔피언으로 잘하는 사람" 을 참고용으로 보여주려면 이름이 필요하다.
                    f.write(json.dumps({
                        "match_id": mid, "date": day, "patch": patch,
                        "champion": p.get("championName"),
                        "position": p.get("teamPosition") or "",
                        "win": bool(p.get("win")),
                        "name": (p.get("riotIdGameName") or "").strip(),
                        "tag": p.get("riotIdTagline") or "",
                    }, ensure_ascii=False) + "\n")
                added += 1
                if added % 50 == 0:
                    f.flush()
                    print(f"  … {added:,}판 수집 (계정 {i}/{len(players)})")

    print(f"[수집] 이번 실행에서 {added:,}판 추가 · 누적 {len(seen):,}판")
    aggregate()


def aggregate():
    """원본을 챔피언 x 라인 승률표로 집계한다."""
    if not os.path.exists(RAW):
        print("[집계] 원본이 없습니다"); return
    import pandas as pd

    rows = []
    with open(RAW, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if not rows:
        print("[집계] 비어 있습니다"); return

    df = pd.DataFrame(rows)
    df = df[df["position"].isin(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"])]
    g = df.groupby(["champion", "position"]).agg(
        경기수=("win", "size"), 승률=("win", "mean")).reset_index()
    # 픽률 = 그 라인 전체 경기 중 이 챔피언이 나온 비율
    per_pos = df.groupby("position").size().rename("라인_전체")
    g = g.join(per_pos, on="position")
    g["픽률"] = g["경기수"] / g["라인_전체"]
    g = g[g["경기수"] >= 5].copy()          # 표본이 너무 적으면 승률이 의미 없다
    g["승률"] = g["승률"].round(4)
    g["픽률"] = g["픽률"].round(4)
    g = g.sort_values(["position", "승률"], ascending=[True, False])
    g[["champion", "position", "경기수", "승률", "픽률"]].to_csv(OUT, index=False, encoding="utf-8-sig")

    # 챔피언 x 라인별 "잘하는 사람" — 공부용 참고.
    # 표본이 적으면 승률이 의미 없다 — 기준은 아래 필터에 있다.
    if "name" in df.columns:
        pl = df[df["name"].astype(str).str.len() > 0]
        if len(pl):
            pg = pl.groupby(["champion", "position", "name", "tag"]).agg(
                판수=("win", "size"), 승률=("win", "mean")).reset_index()
            # 표본이 먼저다. 3판 100% 는 동전 세 번 앞면(12.5%)과 다르지 않아 참고가 안 된다.
            # 8판 이상 & 승률 50% 초과만 "잘하는 유저" 로 본다.
            pg = pg[(pg["판수"] >= 8) & (pg["승률"] > 0.5)].sort_values(
                ["champion", "position", "승률", "판수"], ascending=[True, True, False, False])
            pg = pg.groupby(["champion", "position"]).head(5)
            pg["승률"] = pg["승률"].round(4)
            pg.to_csv("reports/tables/champion_top_players.csv", index=False, encoding="utf-8-sig")
            print(f"[집계] 상위 플레이어 {len(pg):,}행")

    # 화면에 나가는 수는 이 하나로 고정한다 —
    # "라인이 확인되고 11분 이상 진행된, 중복 없는 경기 수".
    # (원본 줄 수 / 필터 전 수 / 참가자 수 를 섞어 말하면 값이 계속 달라 보인다)
    meta = {"수집_경기수": int(df["match_id"].nunique()),
            "정의": "라인 정보가 있고 11분 이상 진행된 중복 없는 경기 수",
            "패치": sorted(df["patch"].dropna().unique().tolist())[-3:],
            "기간": f"{df['date'].min()} ~ {df['date'].max()}",
            "갱신": time.strftime("%Y-%m-%d %H:%M")}
    with open("reports/tables/champion_stats_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[집계] {len(g):,}개 조합 · 경기 {meta['수집_경기수']:,}판 · {meta['기간']}")
    print(f"[저장] {OUT}")


if __name__ == "__main__":
    main()
