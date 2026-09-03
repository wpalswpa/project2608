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
#   경기 하나당 참가자 10명 → (챔피언, 라인, 승패, 날짜) 10건.
#   개인 식별 정보는 저장하지 않는다 — 집계에 필요 없다.
#
# 산출물:
#   data/champion_raw.jsonl        수집 원본 (저장소에 안 올린다 — 크고 재생성 가능)
#   reports/tables/champion_stats.csv  집계 결과 (이건 올린다)
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

from riot_api import PLATFORM, ROUTING, SOLO_QUEUE, RiotApiError, _get  # noqa: E402

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
            entries = _get(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/{t}"
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
                ids = _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/"
                           f"by-puuid/{pu}/ids?queue={SOLO_QUEUE}&count={args.per_player}")
            except RiotApiError:
                continue

            for mid in ids:
                if mid in seen or time.time() > deadline:
                    continue
                try:
                    info = _get(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")["info"]
                except RiotApiError:
                    continue
                seen.add(mid)
                if info.get("gameDuration", 0) < MIN_DURATION:
                    continue
                patch = ".".join((info.get("gameVersion") or "").split(".")[:2])
                day = time.strftime("%Y-%m-%d", time.localtime(info.get("gameCreation", 0) / 1000))
                for p in info["participants"]:
                    # 개인 식별 정보는 담지 않는다 — 집계에 불필요하다
                    f.write(json.dumps({
                        "match_id": mid, "date": day, "patch": patch,
                        "champion": p.get("championName"),
                        "position": p.get("teamPosition") or "",
                        "win": bool(p.get("win")),
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

    meta = {"수집_경기수": int(df["match_id"].nunique()),
            "패치": sorted(df["patch"].dropna().unique().tolist())[-3:],
            "기간": f"{df['date'].min()} ~ {df['date'].max()}",
            "갱신": time.strftime("%Y-%m-%d %H:%M")}
    with open("reports/tables/champion_stats_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[집계] {len(g):,}개 조합 · 경기 {meta['수집_경기수']:,}판 · {meta['기간']}")
    print(f"[저장] {OUT}")


if __name__ == "__main__":
    main()
