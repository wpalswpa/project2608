# 경로 문제 해결 — 어디서 실행하든 프로젝트 폴더를 찾아준다
#
# 왜 필요한가: 스크립트가 "data/high_diamond_ranked_10min.csv" 같은 상대경로를 쓰면
# 프로젝트 루트에서 실행할 때만 동작한다. src/ 안에서 돌리거나 주피터에서 열면
# "No such file or directory" 가 난다. 이 모듈이 프로젝트 루트를 찾아 그리로 이동시킨다.
#
# 사용 (스크립트 맨 위에 두 줄):
#   from paths import cd_root
#   cd_root()
import os
from pathlib import Path

# 프로젝트 루트임을 알아보는 표시 — 둘 다 있어야 진짜 루트
MARKERS = ("data", "predict.py")


def find_root(start: Path | None = None) -> Path:
    """현재(또는 지정) 위치에서 위로 올라가며 프로젝트 루트를 찾는다."""
    here = (start or Path(__file__).resolve().parent)
    for p in [here, *here.parents][:6]:
        if (p / MARKERS[0]).is_dir() and (p / MARKERS[1]).is_file():
            return p
    # 파일 위치로 못 찾으면 현재 작업 폴더 기준으로 한 번 더
    here = Path.cwd()
    for p in [here, *here.parents][:6]:
        if (p / MARKERS[0]).is_dir() and (p / MARKERS[1]).is_file():
            return p
    raise FileNotFoundError(
        "프로젝트 폴더를 찾지 못했습니다. "
        "'data' 폴더와 'predict.py' 가 함께 있는 폴더 안에서 실행해 주세요.")


def cd_root(verbose: bool = False) -> Path:
    """프로젝트 루트로 작업 폴더를 옮긴다. 이후 상대경로가 항상 통한다."""
    root = find_root()
    os.chdir(root)
    if verbose:
        print(f"[paths] 작업 폴더: {root}")
    return root


if __name__ == "__main__":
    r = cd_root(verbose=True)
    need = ["data/high_diamond_ranked_10min.csv", "data/splits/train_idx.csv",
            "data/splits/test_idx.csv", "artifacts/model.joblib",
            "artifacts/schema.json"]
    print("\n필요한 파일 확인")
    for f in need:
        print(f"  {'있음' if (r / f).exists() else '없음 ❗'}  {f}")
    opt = "data/oracles_elixir_2022_match_data.csv"
    print(f"  {'있음' if (r / opt).exists() else '없음(실험 B만 못 돌림)'}  {opt}")
