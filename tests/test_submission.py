"""제출 폴더(final/) 계약 — 채점자가 열었을 때 실제로 도는지 본다.

이 테스트가 없어서 놓쳤던 것:
  기존 검사는 "final/ 에 파일 6개가 있는가"만 봤다. 그런데 개발 PC 는
  `pip install -e .` 로 lolwin 이 설치돼 있어, final/5_predict.py 가
  lolwin 을 import 해도 그냥 돌았다. 채점자 환경(설치 없음)에서만 죽는
  결함이라 로컬에서는 영원히 안 보인다.

  그래서 여기서는 sys.path 와 메타 경로 훅에서 저장소를 지운 하위 프로세스로
  돌려, "lolwin 이 없는 환경"을 흉내 낸다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "final")

EXPECTED = [
    "1_README.md",
    "2_최종_노트북.ipynb",
    "3_model.joblib",
    "4_schema.json",
    "5_predict.py",
    "6_model_card.md",
]


def test_제출물은_정확히_6개다():
    assert sorted(os.listdir(FINAL)) == sorted(EXPECTED)


def test_predict_는_lolwin_없이도_돈다():
    """final/5_predict.py --demo 가 저장소와 무관하게 종료코드 0 으로 끝나야 한다.

    저장소 경로를 sys.path 에서 빼는 것만으로는 부족하다 — editable 설치는
    sys.meta_path 에 finder 를 심기 때문이다. 둘 다 제거한다.
    """
    bootstrap = textwrap.dedent(
        f"""
        import sys, runpy
        root = {ROOT!r}
        sys.path = [p for p in sys.path if os.path.abspath(p) != os.path.abspath(root)] if (os := __import__("os")) else sys.path
        sys.meta_path = [f for f in sys.meta_path
                         if "editable" not in type(f).__module__.lower()
                         and "editable" not in getattr(f, "__name__", "").lower()]
        for m in [m for m in sys.modules if m.startswith("lolwin")]:
            del sys.modules[m]
        sys.argv = ["5_predict.py", "--demo"]
        runpy.run_path("5_predict.py", run_name="__main__")
        """
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run(
        [sys.executable, "-B", "-c", bootstrap],
        cwd=FINAL, env=env, capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == 0, f"final/5_predict.py 가 단독 실행에서 실패했다:\n{r.stderr[-1500:]}"
    assert "블루 승리 확률" in r.stdout


def test_predict_는_lolwin_을_import_하지_않는다():
    """소스 수준에서도 의존이 없어야 한다 (설치돼 있어도 우연히 통과하지 않도록)."""
    src = open(os.path.join(FINAL, "5_predict.py"), encoding="utf-8").read()
    assert not re.search(r"^\s*(from|import)\s+lolwin", src, re.M), \
        "final/5_predict.py 가 lolwin 을 import 한다 — 자급형이어야 한다"


def test_제출본_predict_는_정본과_같은_결과를_낸다():
    """자급형으로 다시 쓴 로직이 lolwin/predict.py 와 갈라지지 않았는지."""
    sys.path.insert(0, ROOT)
    from lolwin.predict import DEMOS, predict as reference

    # exec_module 은 final/ 에 __pycache__ 를 남긴다 — 제출물 6개 원칙이 깨지므로 끈다
    prev, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("_sub", os.path.join(FINAL, "5_predict.py"))
        sub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sub)
    finally:
        sys.dont_write_bytecode = prev

    for name, payload in DEMOS:
        assert sub.predict(payload) == reference(payload), f"'{name}' 에서 결과가 갈라졌다"


def test_README_상대링크가_final_기준으로_살아있다():
    """저장소 안에서 final/1_README.md 를 열어도 그림·문서가 보여야 한다."""
    src = open(os.path.join(FINAL, "1_README.md"), encoding="utf-8").read()
    links = re.findall(r"\]\((?!https?://|#)([^)]+)\)", src)
    broken = [l for l in links
              if l.split("#")[0] and not os.path.exists(os.path.join(FINAL, l.split("#")[0]))]
    assert not broken, f"깨진 상대링크 {len(broken)}개: {broken[:5]}"


def test_schema_와_model_이_짝이_맞는다():
    """스키마의 피처 수와 모델이 기대하는 입력 차원이 같아야 한다."""
    import joblib

    schema = json.load(open(os.path.join(FINAL, "4_schema.json"), encoding="utf-8"))
    model = joblib.load(os.path.join(FINAL, "3_model.joblib"))
    n_schema = len(schema["features"])
    n_model = model.named_steps["model"].coef_.shape[1]
    assert n_schema == n_model, f"스키마 {n_schema}피처 vs 모델 {n_model}입력 — 어긋났다"
