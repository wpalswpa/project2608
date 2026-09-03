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
import os
import shutil
import sys

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

def main():
    os.makedirs(OUT, exist_ok=True)
    missing = [src for src, _, _ in ITEMS if not os.path.exists(src)]
    if missing:
        print("[실패] 원본이 없습니다:", ", ".join(missing))
        return 1

    for i, (src, dst, desc) in enumerate(ITEMS, 1):
        shutil.copy2(src, os.path.join(OUT, dst))
        print(f"  {i}. {dst:<22} ← {src}")

    print(f"\n[완료] {OUT}/ 에 제출물 6개 (그 외 파일 없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
