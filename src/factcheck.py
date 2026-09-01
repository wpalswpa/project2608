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

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
issues = []


def read(p):
    return io.open(p, encoding="utf-8").read()


DOCS = ["README.md", "model_card.md"] + sorted(glob.glob("docs/*.md"))
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
code = re.findall(r'"(\w+)"', re.search(
    r"DIFF13 = \[(.*?)\]", read("src/finalize_model.py"), re.S).group(1))
if feats != code:
    issues.append(f"[피처 불일치] schema {len(feats)}개 ≠ finalize_model {len(code)}개")
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

# 7) requirements.txt 가 실제로 쓰는 패키지를 덮는가
reqs = read("requirements.txt").lower()
for pkg in ["flask", "scikit-learn", "pandas", "numpy", "matplotlib", "joblib", "pymysql"]:
    if pkg not in reqs:
        issues.append(f"[requirements 누락] {pkg}")

print(f"점검 문서 {len(DOCS)}개 · 발견된 문제 {len(issues)}건")
for i in issues:
    print("  -", i)
if not issues:
    print("  문서와 코드가 서로 어긋나는 곳이 없습니다.")
