# 티어별 일반화 검증 — 다이아로 학습한 모델이 다른 티어에서도 통하는가
#
# 실행:
#   python src/tier_generalization.py --collect --tier IRON --games 300
#   python src/tier_generalization.py --report          (모은 것으로 채점·그림)
#
# 왜 하나:
#   모델은 Kaggle 다이아 랭크 9,879판으로 학습했다. model_card 에 "티어 교차 적용
#   금지" 를 한계로 적어뒀지만, 실제로 얼마나 떨어지는지는 재본 적이 없다.
#   "쓰면 안 된다" 보다 "이만큼 떨어진다" 가 훨씬 쓸모 있는 한계다.
#
# 예상이 갈리는 지점 (그래서 재봐야 한다):
#   - 떨어질 이유: 저티어는 10분 이후 변수가 크다. 한 명이 무너지는 판이 많아
#     초반 격차가 덜 유지된다 — 우리 모델의 전제(스노우볼)가 약해진다.
#   - 오를 이유:   저티어는 실력 편차가 커서 10분에 이미 크게 벌어진 판이 많다.
#     우리 모델은 크게 벌어진 판을 0.947 로 맞힌다 — 그 비중이 늘면 정확도가 오른다.
#   둘이 반대로 작용하므로 실측 없이는 방향조차 알 수 없다.
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

if not os.environ.get("RIOT_API_KEY") and os.path.exists(".env"):
    for _line in open(".env", encoding="utf-8"):
        if _line.strip().startswith("RIOT_API_KEY="):
            os.environ["RIOT_API_KEY"] = _line.split("=", 1)[1].strip()

from riot_api import (LAST_APP_COUNT, PLATFORM, ROUTING,  # noqa: E402
                      RateLimited, RiotApiError, SOLO_QUEUE, _get,
                      timeline_to_diff13)

RAW = "data/tier_raw.jsonl"          # gitignore — 수집 원본
OUT = "reports/tables/tier_accuracy.csv"
FIG = "reports/figures/tier_accuracy.png"
TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
PACE_SEC = 1.25
RESERVE = 70                          # 라이브 사용자 몫을 남긴다 (다른 수집기와 같은 기준)
_last = [0.0]


def get_paced(url: str, tries: int = 4) -> dict:
    for _ in range(tries):
        gap = PACE_SEC - (time.time() - _last[0])
        if gap > 0:
            time.sleep(gap)
        _last[0] = time.time()
        try:
            r = _get(url)
            if LAST_APP_COUNT[0] >= RESERVE:
                print(f"  [양보] 예산 {LAST_APP_COUNT[0]}/100 — 20초 쉽니다")
                time.sleep(20)
            return r
        except RateLimited as e:
            print(f"  [대기] {e.retry_after}초")
            time.sleep(e.retry_after + 1)
    raise RiotApiError("한도가 계속 걸립니다.")


def seen_ids() -> set:
    s = set()
    if os.path.exists(RAW):
        with open(RAW, encoding="utf-8") as f:
            for line in f:
                try:
                    s.add(json.loads(line)["match_id"])
                except Exception:
                    continue
    return s


def collect(tier: str, want: int):
    """한 티어의 경기를 모아 10분 피처 + 실제 승패를 기록한다."""
    os.makedirs("data", exist_ok=True)
    seen = seen_ids()
    print(f"[{tier}] 목표 {want}판 · 이미 받은 경기 {len(seen):,}건은 건너뜁니다")

    puuids = []
    for div in ("I", "II", "III"):
        try:
            entries = get_paced(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/"
                                f"entries/RANKED_SOLO_5x5/{tier}/{div}?page=1")
        except RiotApiError:
            continue
        puuids += [e["puuid"] for e in entries if e.get("puuid")]
        if len(puuids) >= 120:
            break
    print(f"  표본 계정 {len(puuids):,}명")

    added = 0
    with open(RAW, "a", encoding="utf-8") as f:
        for pu in puuids:
            if added >= want:
                break
            try:
                ids = get_paced(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/"
                                f"by-puuid/{pu}/ids?queue={SOLO_QUEUE}&count=5")
            except RiotApiError:
                continue
            for mid in ids:
                if mid in seen or added >= want:
                    continue
                seen.add(mid)
                try:
                    info = get_paced(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")["info"]
                    if info.get("gameDuration", 0) < 660:
                        continue
                    blue = {p["participantId"] for p in info["participants"] if p["teamId"] == 100}
                    red = {p["participantId"] for p in info["participants"] if p["teamId"] == 200}
                    tl = get_paced(f"https://{ROUTING}.api.riotgames.com/lol/match/v5/"
                                   f"matches/{mid}/timeline")
                    feats = timeline_to_diff13(tl, blue, red)
                except (RiotApiError, KeyError, IndexError):
                    continue
                blue_won = next(t["win"] for t in info["teams"] if t["teamId"] == 100)
                # 개인 식별 정보는 담지 않는다 — 티어별 정확도 집계에 불필요하다
                f.write(json.dumps({"match_id": mid, "tier": tier,
                                    "y": int(blue_won), **feats}, ensure_ascii=False) + "\n")
                added += 1
                if added % 20 == 0:
                    f.flush()
                    print(f"  … {added}/{want}판")
    print(f"[{tier}] {added}판 추가")


def report():
    """모은 경기를 **학습 때와 같은 모델**로 채점해 티어별 정확도를 낸다."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
        if any(_f == x.name for x in matplotlib.font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = _f
            break
    plt.rcParams["axes.unicode_minus"] = False

    from lolwin.features import DIFF13, GOLD_BINS, GOLD_BIN_LABELS
    from lolwin.predict import predict

    if not os.path.exists(RAW):
        print("수집 원본이 없습니다. --collect 부터 실행하세요."); return
    rows = [json.loads(l) for l in open(RAW, encoding="utf-8") if l.strip()]
    df = pd.DataFrame(rows).drop_duplicates("match_id")
    if df.empty:
        print("비어 있습니다."); return

    df["p"] = [predict({f: float(r[f]) for f in DIFF13})["win_prob_blue"]
               for _, r in df.iterrows()]
    df["맞힘"] = ((df["p"] >= 0.5).astype(int) == df["y"]).astype(int)
    df["격차"] = df["GoldDiff"].abs()
    df["구간"] = pd.cut(df["격차"], bins=GOLD_BINS, labels=GOLD_BIN_LABELS, right=False)

    g = df.groupby("tier").agg(경기수=("맞힘", "size"), 정확도=("맞힘", "mean"),
                               평균골드차=("격차", "mean")).reset_index()
    # 크게 벌어진 판의 비중 — "저티어는 격차가 커서 오히려 잘 맞는다" 가설을 보는 열
    big = df[df["격차"] >= 2500].groupby("tier").size().rename("크게벌어진판")
    g = g.join(big, on="tier").fillna({"크게벌어진판": 0})
    g["크게벌어진비율"] = (g["크게벌어진판"] / g["경기수"]).round(4)
    g["정확도"] = g["정확도"].round(4)
    g["평균골드차"] = g["평균골드차"].round(0)
    order = {t: i for i, t in enumerate(TIERS)}
    g = g.sort_values("tier", key=lambda s: s.map(lambda x: order.get(x, 99)))
    os.makedirs("reports/tables", exist_ok=True)
    g.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(g.to_string(index=False))

    # 그림: 티어별 정확도 + 학습 티어(다이아) 기준선
    KO = {"IRON": "아이언", "BRONZE": "브론즈", "SILVER": "실버", "GOLD": "골드",
          "PLATINUM": "플래티넘", "EMERALD": "에메랄드", "DIAMOND": "다이아몬드"}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    labels = [KO.get(t, t) for t in g["tier"]]
    bars = ax.bar(labels, g["정확도"], color=["#2f6fe4" if t == "DIAMOND" else "#9aa5b1"
                                              for t in g["tier"]], width=0.6)
    for b, acc, n in zip(bars, g["정확도"], g["경기수"]):
        ax.text(b.get_x() + b.get_width() / 2, acc + .008, f"{acc:.3f}",
                ha="center", fontsize=10, fontweight="bold")
        ax.text(b.get_x() + b.get_width() / 2, .52, f"{n}판", ha="center",
                fontsize=8.5, color="white")
    ax.axhline(0.7394, color="black", ls="--", lw=1.2, label="학습 티어(다이아) 홀드아웃 0.7394")
    ax.axhline(0.5, color="gray", ls=":", lw=1, label="찍기 0.5")
    ax.set_ylim(0.45, 1.0)
    ax.set_ylabel("정확도")
    ax.legend(fontsize=9, loc="upper left")
    ax.set_title("티어를 바꾸면 정확도가 어떻게 되나 — 같은 모델, 다른 티어 경기",
                 fontsize=12.5, pad=10)
    fig.tight_layout()
    os.makedirs("reports/figures", exist_ok=True)
    fig.savefig(FIG, dpi=130, bbox_inches="tight")
    print(f"[저장] {OUT} · {FIG}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--tier", default="IRON", choices=TIERS)
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.collect:
        collect(a.tier, a.games)
    if a.report or not a.collect:
        report()


if __name__ == "__main__":
    main()
