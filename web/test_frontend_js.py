# 화면 JS 부팅 검사 — 최상위에서 쓰는 이름이 최상위에 선언돼 있는가
#
# 실행: python web/test_frontend_js.py
#
# 왜 필요한가:
#   선언 블록이 실수로 다른 함수 안에 들어가면, 문법은 멀쩡한데 최상위 실행이
#   ReferenceError 로 죽는다. 그러면 그 아래 이벤트 바인딩이 전부 실행되지 않아
#   화면이 통째로 먹통이 된다 — 실제로 그렇게 배포된 적이 있다(57cac35).
#   node --check(문법)로는 안 잡히고, API 스모크로도 안 잡힌다. 화면만 죽기 때문이다.
#
#   node 가 있으면 DOM 스텁으로 실제 부팅까지 해보고, 없으면 정적으로 스코프를 본다.
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "web", "templates", "index.html")

# 최상위에서 호출·참조되므로 반드시 최상위에 선언돼야 하는 이름들
MUST_BE_TOP = ["CHAMP_KO", "champKo", "loadChampNames", "TIER_SHORT",
               "confBins", "DDRAGON", "DDV", "showTab", "loadSummoner", "loadReport"]


def _script(html: str) -> str:
    m = re.search(r"<script>\s*\"use strict\";(.*?)</script>", html, re.S)
    assert m, "인라인 <script> 를 찾지 못했습니다"
    return m.group(1)


def _top_level_names(js: str) -> set:
    """중괄호 깊이 0에서 선언된 이름만 모은다."""
    names, depth = set(), 0
    for line in js.splitlines():
        stripped = line.strip()
        if depth == 0 and re.match(r"(const|let|var|function|async function)\s", stripped):
            m = re.search(r"(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)", stripped)
            if m:
                names.add(m.group(1))
        # 문자열·주석 안의 괄호까지 세지는 않지만, 선언 줄 판정에는 충분하다
        depth += line.count("{") - line.count("}")
    return names


def test_top_level_declarations():
    """최상위에서 쓰는 이름이 함수 안에 갇혀 있지 않은가."""
    html = open(TEMPLATE, encoding="utf-8").read()
    # Jinja 조건은 정적 검사에 방해가 되므로 참 가지로 펼친다
    html = re.sub(r"\{%\s*if [^%]*%\}", "", html)
    html = re.sub(r"\{%\s*else\s*%\}.*?\{%\s*endif\s*%\}", "", html, flags=re.S)
    html = re.sub(r"\{%\s*endif\s*%\}|\{\{[^}]*\}\}", "", html)
    top = _top_level_names(_script(html))
    missing = [n for n in MUST_BE_TOP if n not in top]
    assert not missing, ("최상위에 없는 선언: " + ", ".join(missing) +
                         " — 다른 함수 안에 들어갔는지 확인하세요. "
                         "최상위 실행이 ReferenceError 로 죽으면 화면 전체가 먹통이 됩니다.")


def test_boots_in_node():
    """node 가 있으면 DOM 스텁으로 실제 부팅까지 해본다 (없으면 건너뜀)."""
    if not shutil.which("node"):
        print("  [건너뜀] node 없음 — 정적 검사로 대체")
        return
    html = open(TEMPLATE, encoding="utf-8").read()
    html = re.sub(r"\{%\s*if [^%]*%\}", "", html)
    html = re.sub(r"\{%\s*else\s*%\}.*?\{%\s*endif\s*%\}", "", html, flags=re.S)
    html = re.sub(r"\{%\s*endif\s*%\}|\{\{[^}]*\}\}", "", html)
    js = _script(html)

    stub = """
const _el = new Proxy({}, {get:(t,p)=>{
  if(p==="addEventListener"||p==="setAttribute"||p==="appendChild") return ()=>{};
  if(p==="querySelectorAll"||p==="querySelector") return ()=>p==="querySelectorAll"?[]:_el;
  if(p==="classList") return {toggle:()=>{},add:()=>{},remove:()=>{}};
  if(p==="dataset"||p==="style") return {};
  return "";
}});
global.document = {querySelector:()=>_el, querySelectorAll:()=>[], getElementById:()=>_el,
  addEventListener:()=>{}, documentElement:{setAttribute:()=>{}, getAttribute:()=>"light"},
  createElement:()=>_el};
global.window = {scrollTo:()=>{}};
global.fetch = () => Promise.resolve({ok:true, json:()=>Promise.resolve({}), status:200});
global.localStorage = {getItem:()=>null, setItem:()=>{}};
global.matchMedia = () => ({matches:false});
global.CSS = {escape:s=>s};
global.setInterval = () => 0;
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(stub + "\n" + js + "\nconsole.log('BOOT_OK');\n")
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
        assert "BOOT_OK" in r.stdout, ("최상위 실행이 실패했습니다:\n" + (r.stderr or "")[:600])
    finally:
        os.unlink(path)


def main():
    failed = 0
    for t in (test_top_level_declarations, test_boots_in_node):
        try:
            t()
            print(f"[통과] {t.__name__} — {t.__doc__.splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"[실패] {t.__name__}\n  {e}")
    print()
    print("화면 JS 가 최상위에서 정상 실행됩니다." if not failed
          else f"{failed}건 실패 — 화면이 먹통일 수 있습니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
