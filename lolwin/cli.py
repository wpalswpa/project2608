"""명령행 진입점 — `lolwin-predict` 또는 `python -m lolwin.cli`."""
from __future__ import annotations

import json
import sys

from lolwin.predict import DEMOS, predict


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] not in ("--demo", "-d"):
        try:
            cases = [("입력", json.loads(sys.argv[1]))]
        except json.JSONDecodeError as e:
            print(f"JSON 을 읽지 못했습니다: {e}", file=sys.stderr)
            return 2
    else:
        cases = DEMOS

    for name, payload in cases:
        try:
            r = predict(payload)
        except ValueError as e:
            print(f"[{name}] {e}", file=sys.stderr)
            return 1
        print(f"\n=== {name} ===")
        print(f"  블루 승리 확률 {r['win_prob_blue']:.1%} → {r['pred_label']}")
        for tf in r["top_factors"][:3]:
            print(f"  · {tf['name']} = {tf['value']} "
                  f"({tf['direction']}, 기여 {tf['contribution']:+.3f})")
        for w in r["warnings"]:
            print(f"  ⚠ {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
