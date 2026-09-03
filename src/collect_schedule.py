# 프로 경기 일정 수집 — 승부예측 투표에 쓸 "가까운 시일 내 경기"
#
# 실행: python src/collect_schedule.py
#
# 출처와 한계를 먼저 밝힌다:
#   Riot 공식 개발자 API 에는 e스포츠 일정 엔드포인트가 없다(승인받은 39개 메서드에도 없다).
#   여기서 쓰는 lolesports 일정 API 는 공식 문서에 없는 비공식 경로다.
#   그래서 **서비스는 이 API 를 직접 부르지 않는다.** 여기서 CSV 로 굳히고
#   웹은 그 파일만 읽는다 — 랭킹·챔피언 수집과 같은 구조다.
#   출처가 막히면 이 스크립트만 바꾸면 되고, 서비스는 그대로 돈다.
#
# 산출물: reports/tables/schedule.csv
import csv
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

OUT = "reports/tables/schedule.csv"
API = "https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=ko-KR&sport=lol"
KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"   # lolesports.com 프런트에 공개된 키

# 한국 사용자가 아는 리그를 위로 올린다. 목록에 없는 리그는 그 아래로 간다.
PRIORITY = ["LCK", "LCK CL", "LCK Academy", "LPL", "LEC", "LCS", "MSI", "Worlds",
            "EMEA Masters", "LJL", "PCS", "VCS"]


def fetch() -> list:
    req = urllib.request.Request(API, headers={
        "x-api-key": KEY,
        "User-Agent": "Mozilla/5.0 (team-project; LoL win-prediction; educational)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["data"]["schedule"]["events"]


def main():
    try:
        events = fetch()
    except Exception as e:
        print(f"[실패] 일정을 받지 못했습니다: {e}")
        print("       서비스는 기존 CSV 로 계속 동작합니다.")
        return 1

    rows = []
    for e in events:
        if e.get("state") != "unstarted":
            continue                       # 아직 시작 안 한 경기만 투표 대상
        m = e.get("match") or {}
        teams = m.get("teams") or []
        if len(teams) != 2:
            continue
        # 대진이 아직 안 정해진 경기(TBD)는 투표할 수 없다
        if any(t.get("name", "").upper() in ("TBD", "") for t in teams):
            continue
        league = (e.get("league") or {}).get("name", "")
        rows.append({
            "match_id": m.get("id", ""),
            "start_at": e.get("startTime", ""),          # UTC ISO8601
            "league": league,
            "block": e.get("blockName", "") or "",
            "bo": (m.get("strategy") or {}).get("count", ""),
            "team1": teams[0].get("name", ""),
            "team1_code": teams[0].get("code", ""),
            "team1_img": teams[0].get("image", ""),
            "team2": teams[1].get("name", ""),
            "team2_code": teams[1].get("code", ""),
            "team2_img": teams[1].get("image", ""),
            "priority": PRIORITY.index(league) if league in PRIORITY else 99,
        })

    rows.sort(key=lambda r: (r["priority"], r["start_at"]))
    os.makedirs("reports/tables", exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else
                           ["match_id", "start_at", "league", "block", "bo",
                            "team1", "team1_code", "team1_img",
                            "team2", "team2_code", "team2_img", "priority"])
        w.writeheader()
        w.writerows(rows)

    meta = {"경기수": len(rows), "갱신": time.strftime("%Y-%m-%d %H:%M"),
            "설명": "아직 시작하지 않은 프로 경기 일정 (투표 대상)"}
    with open("reports/tables/schedule_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print(f"[완료] 예정 경기 {len(rows)}건")
    for r in rows[:5]:
        print(f"   {r['start_at'][:16]}  {r['league']:<10} {r['team1']} vs {r['team2']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
