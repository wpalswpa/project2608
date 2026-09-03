# 솔로랭크 상위 1,000명 랭킹 수집
#
# 실행: python src/collect_ranking.py [--limit 1000]
#
# 왜 배치인가:
#   league-v4 는 puuid·LP·전적만 주고 **이름을 주지 않는다**. 이름을 붙이려면
#   account-v1 을 1인당 한 번씩 불러야 하는데, 1,000명이면 1,000회다.
#   Riot 예산이 100회/120초라 라이브 요청 안에서는 불가능하다(20분 걸린다).
#   그래서 여기서 한 번 모아 CSV 로 굳히고, 서비스는 그 CSV 만 읽는다.
#
# 이어받기: 이미 이름을 받은 puuid 는 기존 CSV 에서 재사용한다.
#   중간에 끊겨도 다시 실행하면 못 받은 사람부터 이어서 받는다.
#
# 산출물: reports/tables/ranking.csv (커밋) + ranking_meta.json
import argparse
import csv
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

# .env 직접 읽기 — 서버는 check_project.sh 가 넣어주지만 이 스크립트는 혼자 돈다
if not os.environ.get("RIOT_API_KEY") and os.path.exists(".env"):
    for _line in open(".env", encoding="utf-8"):
        if _line.strip().startswith("RIOT_API_KEY="):
            os.environ["RIOT_API_KEY"] = _line.split("=", 1)[1].strip()

from riot_api import PLATFORM, ROUTING, RateLimited, RiotApiError, _get  # noqa: E402

OUT = "reports/tables/ranking.csv"
META = "reports/tables/ranking_meta.json"
PACE_SEC = 1.25          # 라이브와 예산을 나눠 쓰므로 천천히 (collect_champion_stats 와 같은 기준)
_last = [0.0]


def get_paced(url: str, tries: int = 4) -> dict:
    """간격을 지키고, 한도에 걸리면 Retry-After 만큼 온전히 기다린다 (배치 전용)."""
    for _ in range(tries):
        gap = PACE_SEC - (time.time() - _last[0])
        if gap > 0:
            time.sleep(gap)
        _last[0] = time.time()
        try:
            return _get(url)
        except RateLimited as e:
            print(f"  [대기] 한도 초과 — {e.retry_after}초")
            time.sleep(e.retry_after + 1)
    raise RiotApiError("한도가 계속 걸립니다. 나중에 다시 실행하세요.")


def load_known_names() -> dict:
    """이미 받아둔 puuid → 이름. 재실행 때 account-v1 을 다시 부르지 않으려고."""
    known = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("puuid") and r.get("name"):
                    known[r["puuid"]] = (r["name"], r.get("tag", ""))
    return known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000, help="몇 등까지 모을지")
    args = ap.parse_args()
    os.makedirs("reports/tables", exist_ok=True)

    # 챌린저 300 + 그랜드마스터 700 = 정확히 상위 1,000명
    rows = []
    for tier, api in (("CHALLENGER", "challengerleagues"), ("GRANDMASTER", "grandmasterleagues")):
        if len(rows) >= args.limit:
            break
        try:
            entries = get_paced(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/{api}"
                                f"/by-queue/RANKED_SOLO_5x5")["entries"]
        except RiotApiError as e:
            print(f"  [건너뜀] {tier}: {e}")
            continue
        # LP 내림차순이 곧 등수다
        for e in sorted(entries, key=lambda x: -x["leaguePoints"]):
            rows.append({"tier": tier, "puuid": e["puuid"], "lp": e["leaguePoints"],
                         "wins": e["wins"], "losses": e["losses"]})
        print(f"  [{tier}] {len(entries):,}명")

    rows = rows[:args.limit]
    known = load_known_names()
    print(f"[이름] 이미 아는 사람 {len(known):,}명 — 나머지만 조회합니다")

    need = [r for r in rows if r["puuid"] not in known]
    for i, r in enumerate(need, 1):
        try:
            acc = get_paced(f"https://{ROUTING}.api.riotgames.com/riot/account/v1/"
                            f"accounts/by-puuid/{r['puuid']}")
            known[r["puuid"]] = (acc.get("gameName", ""), acc.get("tagLine", ""))
        except RiotApiError:
            known[r["puuid"]] = ("", "")     # 못 받아도 등수는 살린다
        if i % 25 == 0:
            print(f"  … 이름 {i:,}/{len(need):,}")
            _write(rows, known)              # 중간 저장 — 끊겨도 여기까지는 남는다

    _write(rows, known)
    named = sum(1 for r in rows if known.get(r["puuid"], ("",))[0])
    print(f"[완료] {len(rows):,}등까지 · 이름 확보 {named:,}명")


def _write(rows, known):
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "tier", "name", "tag", "lp", "wins", "losses", "puuid"])
        for i, r in enumerate(rows, 1):
            name, tag = known.get(r["puuid"], ("", ""))
            w.writerow([i, r["tier"], name, tag, r["lp"], r["wins"], r["losses"], r["puuid"]])
    import json
    with open(META, "w", encoding="utf-8") as f:
        json.dump({"총원": len(rows), "갱신": time.strftime("%Y-%m-%d %H:%M"),
                   "설명": "솔로랭크 LP 내림차순 상위 1,000명 (챌린저 + 그랜드마스터)"},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
