# 제출물 6종을 한 폴더에 모은다 (final/)
#
# 실행: python scripts/build_submission.py
#
# 왜 복사인가 — 옮기면 안 된다:
#   model.joblib·schema.json·predict.py 는 코드가 경로로 찾는 파일이다.
#   실제로 100곳 넘게 참조하고 있어(테스트·웹서비스·재현 스크립트 전부),
#   위치를 바꾸면 프로젝트가 통째로 깨진다.
#   그래서 원본은 그대로 두고, 제출용으로 한곳에 모아만 둔다.
#   원본이 바뀌면 이 스크립트를 다시 돌리면 된다.
import hashlib
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "final"

# (원본 경로, 제출 폴더에서의 이름, 설명) — 계획서 §6.2 의 필수 산출물 6종
ITEMS = [
    ("README.md",                  "1_README.md",           "문제 정의 · 실행 방법 · 구조"),
    ("reports/model_report.ipynb", "2_최종_노트북.ipynb",     "클린 런타임에서 무오류 실행"),
    ("artifacts/model.joblib",     "3_model.joblib",        "전처리 포함 Pipeline 전체"),
    ("artifacts/schema.json",      "4_schema.json",         "입력 컬럼 · 타입 · 허용 범위"),
    ("predict.py",                 "5_predict.py",          "predict(payload) -> dict"),
    ("model_card.md",              "6_model_card.md",       "용도 · 성능 · 사용 금지 상황"),
]


def sha(path: str, n: int = 8) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def main():
    os.makedirs(OUT, exist_ok=True)
    missing = [src for src, _, _ in ITEMS if not os.path.exists(src)]
    if missing:
        print("[실패] 원본이 없습니다:", ", ".join(missing))
        return 1

    lines = ["# 이 폴더 안내 (제출물이 아닙니다)", "",
             "**제출할 것은 아래 6개 파일입니다. 이 문서는 그 목록일 뿐입니다.**",
             "프로젝트 설명을 보시려면 `1_README.md` 를 여세요.", "",
             "계획서 §6.2 의 필수 산출물입니다. **원본을 복사해 모아둔 것**이라,",
             "고칠 때는 원본을 고치고 `python scripts/build_submission.py` 를 다시 돌리세요.",
             "(원본을 옮기면 코드가 경로로 찾지 못해 프로젝트가 깨집니다)", "",
             "| # | 제출물 | 원본 위치 | 무엇이 들어가는가 |",
             "|---|---|---|---|"]
    for i, (src, dst, desc) in enumerate(ITEMS, 1):
        shutil.copy2(src, os.path.join(OUT, dst))
        lines.append(f"| {i} | `{dst}` | `{src}` | {desc} |")
        print(f"  {i}. {dst:<22} ← {src}")

    lines += ["", "## 무결성 확인", "",
              "복사본이 원본과 같은지 확인하려면 아래 값을 대조하세요 (SHA-256 앞 8자리).", "",
              "| 파일 | 해시 |", "|---|---|"]
    for src, dst, _ in ITEMS:
        lines.append(f"| `{dst}` | `{sha(src)}` |")
    lines += ["", f"생성 시각: {time.strftime('%Y-%m-%d %H:%M')}", ""]

    # 안내문 이름을 README.md 로 하면 제출물 1번(1_README.md)과 헷갈린다.
    # 0_ 을 붙여 맨 위에 오게 하고 이름으로 정체가 드러나게 한다.
    with open(os.path.join(OUT, "0_이_폴더_안내.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"\n[완료] {OUT}/ 에 6종 + 안내 README")
    return 0


if __name__ == "__main__":
    sys.exit(main())
