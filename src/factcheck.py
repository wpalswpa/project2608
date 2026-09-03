# 문서·코드 정합성 자동 점검 — "문서가 하는 말"과 "실제 파일·수치"가 어긋나는 곳을 찾는다
#
# 실행: 프로젝트 폴더에서  python src/factcheck.py
#
# 왜 필요한가: 문서를 고치다 보면 링크가 깨지거나, 수치가 문서마다 달라지거나,
# 폐기한 이름이 남는다. 발표 때 "근거가 뭐냐"는 질문에 버티려면 기계 점검이 필요하다.
# (첫 실행에서 runs.csv 열 어긋남을 실제로 발견했다.)
import glob
import io
import json
import os
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
issues = []


def read(p):
    return io.open(p, encoding="utf-8").read()


# docs 하위 폴더까지 본다 — ddbm-intent/ 가 점검에서 빠져 저장소보다 뒤처진 적이 있다.
# _archive 와 _server_backup 은 계획 시점 보존용이라 제외한다(링크가 깨져 있는 게 정상).
def _live_docs(pattern):
    return sorted(f for f in glob.glob(pattern, recursive=True)
                  if "_archive" not in f and "_server_backup" not in f)


DOCS = (["README.md", "model_card.md", "STUDY.md", "CLAUDE.md"]
        + _live_docs("docs/**/*.md")
        + _live_docs("reports/**/*.md"))   # 발표에 쓰는 문서도 점검 대상
docs = {p: read(p) for p in DOCS}

# 1) 문서가 가리키는 파일이 실제로 있는가 (마크다운 링크 · 백틱 경로)
for p, s in docs.items():
    base = os.path.dirname(p)
    for link in re.findall(r"\]\(([^)#]+?)\)", s):
        if link.startswith("http"):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(base, link))):
            issues.append(f"[깨진 링크] {p} → {link}")
    for path in set(re.findall(
            r"`((?:src|web|docs|data|artifacts|notebooks|reports|db)/[\w가-힣./_]+)`", s)):
        if not os.path.exists(path):
            issues.append(f"[없는 파일 언급] {p} → {path}")

# 2) 산출물 6종이 실제로 있는가
for name, path in {"README": "README.md", "노트북": "notebooks/final_analysis.ipynb",
                   "모델": "artifacts/model.joblib", "스키마": "artifacts/schema.json",
                   "예측함수": "predict.py", "모델카드": "model_card.md"}.items():
    if not os.path.exists(path):
        issues.append(f"[산출물 누락] {name} ({path})")

# 3) 핵심 성능 수치가 schema.json(실측 기록)과 같은가
schema = json.load(open("artifacts/schema.json", encoding="utf-8"))
acc = schema["metrics_holdout"]["accuracy"]
for p, s in docs.items():
    for found in set(re.findall(r"홀드아웃[^\n|]{0,30}?(0\.7\d{3})", s)):
        # 예외: 0.7394(정렬 후 분할) · 0.7136(팀 DB ml_split 분할) — 둘 다 문서가 설명하는 값
        if found not in (f"{acc}", "0.7394", "0.7136"):
            issues.append(f"[수치 확인] {p}: 홀드아웃 {found} (실측 {acc})")

# 4) 피처 목록이 schema · 코드 · 노트북에서 일치하는가
feats = list(schema["features"].keys())
# 정본은 lolwin/features.py 다 (예전엔 학습 스크립트에서 읽었다)
code = re.findall(r'"(\w+)"', re.search(
    r"DIFF13: list\[str\] = \[(.*?)\]", read("lolwin/features.py"), re.S).group(1))
if feats != code:
    issues.append(f"[피처 불일치] schema {len(feats)}개 ≠ lolwin/features {len(code)}개")
# 파이썬 정의와 SQL 뷰가 어긋나면 DB 학습 시 값이 달라진다
sys.path.insert(0, os.getcwd())
from lolwin.features import sql_matches_file
for bad_sql in sql_matches_file():
    issues.append(f"[SQL 불일치] {bad_sql}")
nb = read("notebooks/final_analysis.ipynb")
missing_nb = [f for f in feats if f not in nb]
if missing_nb:
    issues.append(f"[피처 불일치] 노트북에 없는 피처 {missing_nb}")

# 5) runs.csv 열 개수가 헤더와 맞는가
lines = read("runs.csv").strip().split("\n")
ncol = len(lines[0].split(","))
bad = [i for i, l in enumerate(lines[1:], 2) if len(l.split(",")) != ncol]
if bad:
    issues.append(f"[runs.csv 열 어긋남] {bad}번째 줄")

# 6) 폐기한 이름이 남아 있는가
for old in ["진행기록", "관전포인트", "캔버스_정리", "피처_명세", "공부노트",
            "요구명세.md", "연구설계.md", "데이터명세.md", "기술통계.md", "활용가이드.md"]:
    hits = [p for p, s in docs.items() if old in s]
    if hits:
        issues.append(f"[폐기된 이름 '{old}'] {hits}")

# 6-2) 문서가 인용하는 킬 계수가 실측과 같은가
#      (문서마다 −0.144 / −0.11 / −0.107 로 갈렸던 적이 있어 규칙으로 고정한다.
#       근거 파일은 src/feature_reduction.py 가 만든다)
COEF_CSV = "reports/tables/phase2_coef_shift.csv"
if not os.path.exists(COEF_CSV):
    issues.append(f"[근거 파일 없음] {COEF_CSV} — python src/feature_reduction.py 를 먼저 실행")
else:
    rows = {r.split(",")[0]: r.split(",") for r in read(COEF_CSV).strip().split("\n")[1:]}
    with_gold, without_gold = float(rows["KillsDiff"][1]), float(rows["KillsDiff"][2])
    # 문서에 쓸 수 있는 표기: 실측값과 소수 2자리 반올림형
    ok = {f"{abs(with_gold):.3f}", f"{abs(with_gold):.2f}",
          f"{abs(without_gold):.3f}", f"{abs(without_gold):.2f}"}
    # 킬을 언급한 줄에서 "계수/가중치 뒤에 붙은 숫자"만 뽑아 대조한다.
    # (표 안에도 있으므로 줄 단위로 본다. 효과크기 1.09·상관 0.92 는 계수 뒤가 아니라 안 걸린다)
    #  | 를 건너뛰지 않게 막는다 — 표에서 옆 칸(y상관) 값을 계수로 잘못 집는 것을 방지
    NEAR = re.compile(r"(?:계수|가중치)[^0-9\n|]{0,15}[−+-]?(\d\.\d{2,3})")
    for p, s in docs.items():
        for ln, line in enumerate(s.split("\n"), 1):
            if "킬" not in line and "Kills" not in line:
                continue
            for m in NEAR.finditer(line):
                if m.group(1) not in ok:
                    issues.append(f"[계수 확인] {p}:{ln} 킬 계수 {m.group(1)} "
                                  f"(실측 {with_gold:+.3f} · 골드 제외 시 {without_gold:+.3f})")

# 6-3) 대표 정확도가 근거 파일(분할 10회 재학습)과 같은가
#      이 값 하나가 문서 14곳에 적혀 있어, 근거가 바뀌면 어디를 고쳐야 하는지 알려준다.
REPEAT_CSV = "reports/tables/repeat_experimentA.csv"
if not os.path.exists(REPEAT_CSV):
    issues.append(f"[근거 파일 없음] {REPEAT_CSV} — python src/repeat_check.py 를 먼저 실행")
else:
    accs = [float(r.split(",")[1]) for r in read(REPEAT_CSV).strip().split("\n")[1:] if r]
    mean = sum(accs) / len(accs)
    # 문서 표기는 표본표준편차(ddof=1) 기준 — pandas .std() 와 같다
    var = sum((a - mean) ** 2 for a in accs) / (len(accs) - 1)
    mean_s, std_s = f"{mean:.4f}", f"{var ** 0.5:.4f}"
    # "대표 정확도" 라는 이름표가 붙은 값만 본다 ("대표값으로 쓰나" 같은 서술은 제외).
    # 표 안에도 있으므로 | 는 건너뛰되, 이름표가 충분히 구체적이라 옆 칸을 잘못 집지 않는다.
    LABEL = re.compile(r"대표\s*정확도[^0-9\n]{0,12}(0\.\d{4})")
    for p, s in docs.items():
        for ln, line in enumerate(s.split("\n"), 1):
            for m in LABEL.finditer(line):
                if m.group(1) != mean_s:
                    issues.append(f"[대표 정확도] {p}:{ln} {m.group(1)} "
                                  f"(근거 {REPEAT_CSV} 평균 {mean_s})")
                for sd in re.findall(r"±\s*(0\.\d{4})", line[m.end():m.end() + 14]):
                    if sd != std_s:
                        issues.append(f"[대표 정확도] {p}:{ln} 표준편차 {sd} (근거 {std_s})")

# 7) requirements.txt 가 실제로 쓰는 패키지를 덮는가
reqs = read("requirements.txt").lower()
for pkg in ["flask", "scikit-learn", "pandas", "numpy", "matplotlib", "joblib", "pymysql"]:
    if pkg not in reqs:
        issues.append(f"[requirements 누락] {pkg}")


# 8) 지침 문서가 저장소 현실을 따라오는가
#    (docs/ddbm-intent 가 점검에서 빠져 저장소 주소·파이썬 버전이 낡은 채 남아 있었다)
REPO = "wpalswpa/project2608"
for p, s in docs.items():
    for m in re.finditer(r"([\w-]+)/project2608", s):
        if m.group(0) != REPO:
            issues.append(f"[저장소 주소] {p}: {m.group(0)} (실제 {REPO})")
    for ln in s.splitlines():
        # ※ 표시가 붙은 줄은 "계획 시점 기록 + 대체 안내" 라 그대로 둔다
        if "※" in ln:
            continue
        for m in re.finditer(r"[Pp]ython\s*3\.(\d+)", ln):
            if m.group(1) != "11":
                issues.append(f"[파이썬 버전] {p}: 3.{m.group(1)} (실제 3.11)")

# ── model_card 의 유효 범위 표가 schema.json 과 같은가 ──
# 계획서가 요구한 "X 가 a~b 범위일 때만 유효" 를 손으로 적으면 재학습 때 어긋난다.
# 표는 schema 에서 생성했지만, 이후 schema 가 바뀌면 표만 낡을 수 있어 대조한다.
try:
    import json as _json

    _sch = _json.load(open(os.path.join("artifacts", "schema.json"), encoding="utf-8"))["features"]
    _card = read("model_card.md")
    for _f, _v in _sch.items():
        _m = re.search(rf"\| `{re.escape(_f)}` \|[^|]*\| \*\*([^*]+)\*\*", _card)
        if not _m:
            issues.append(f"[유효 범위] model_card.md 에 {_f} 행이 없습니다")
            continue
        _lo, _hi = (x.strip().replace(",", "").replace("+", "") for x in _m.group(1).split("~"))
        for _got, _want, _side in ((_lo, _v["train_min"], "min"), (_hi, _v["train_max"], "max")):
            if abs(float(_got) - float(_want)) > 0.05:
                issues.append(f"[유효 범위] model_card.md {_f} {_side}: {_got} (schema {_want})")
except Exception as _e:
    issues.append(f"[유효 범위] 대조 실패: {_e}")

print(f"점검 문서 {len(DOCS)}개 · 발견된 문제 {len(issues)}건")
for i in issues:
    print("  -", i)
if not issues:
    print("  문서와 코드가 서로 어긋나는 곳이 없습니다.")
