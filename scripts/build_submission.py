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
#
# 다만 두 파일은 그대로 복사하면 제출 폴더에서 깨진다. 복사하며 고친다:
#
#   5_predict.py  루트 predict.py 는 lolwin 패키지를 import 하는 얇은 껍데기다.
#                 개발 PC 는 `pip install -e .` 가 되어 있어 그냥 돌지만,
#                 final/ 만 받은 채점자 환경에서는 ModuleNotFoundError 로 죽는다.
#                 → 옆의 3_model.joblib · 4_schema.json 만 읽는 자급형으로 새로 써 넣는다.
#                 → 로직 정본은 lolwin/predict.py. 두 구현의 출력 일치는
#                   tests/test_submission.py 가 검사한다.
#
#   1_README.md   상대 링크가 저장소 루트 기준이라 final/ 안에서 전부 깨진다(38개).
#                 → docs/ · reports/ · STUDY.md 앞에 ../ 를 붙인다.
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

TEMPLATE_PATH = os.path.join(ROOT, "scripts", "_predict_template.py.txt")


def write_selfcontained_predict(dst):
    """lolwin 의존이 없는 predict 를 만든다. DEMOS 는 정본에서 그대로 가져온다."""
    import pprint
    sys.path.insert(0, ROOT)
    from lolwin.predict import DEMOS

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        body = f.read()
    body = body.replace("__DEMOS__", pprint.pformat(DEMOS, width=96, sort_dicts=False))
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def write_readme_with_fixed_links(src, dst):
    """상대 링크를 final/ 기준으로 한 단계 올린다. 반환: 고친 개수."""
    import re
    with open(src, encoding="utf-8") as f:
        text = f.read()
    text, n = re.subn(
        r"\]\((?!https?://|#|\.\./)(docs/|reports/|STUDY\.md)",
        r"](../\1",
        text,
    )
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    missing = [src for src, _, _ in ITEMS if not os.path.exists(src)]
    if missing:
        print("[실패] 원본이 없습니다:", ", ".join(missing))
        return 1

    for i, (src, dst, desc) in enumerate(ITEMS, 1):
        out = os.path.join(OUT, dst)
        if dst == "5_predict.py":
            write_selfcontained_predict(out)
            print(f"  {i}. {dst:<22} ← 자급형 생성 (lolwin 의존 제거)")
        elif dst == "1_README.md":
            n = write_readme_with_fixed_links(src, out)
            print(f"  {i}. {dst:<22} ← {src}  (상대 링크 {n}개 ../ 보정)")
        else:
            shutil.copy2(src, out)
            print(f"  {i}. {dst:<22} ← {src}")

    print(f"\n[완료] {OUT}/ 에 제출물 6개 (그 외 파일 없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
