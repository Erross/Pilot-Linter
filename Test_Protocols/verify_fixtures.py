"""
Verify every fixture triggers its target rule.
Also report any unexpected cross-triggered rules so we can see what
collateral findings each fixture produces.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ppxml_linter
from generate_fixtures import FIXTURES

FIXTURES_DIR = "test_fixtures"

def verify_one(fx):
    path = os.path.join(FIXTURES_DIR, fx["filename"])
    try:
        parser, findings = ppxml_linter.run_lint(path)
    except Exception as e:
        return {
            "rule_id": fx["rule_id"],
            "filename": fx["filename"],
            "parse_ok": False,
            "target_hit": False,
            "all_rules": [],
            "error": str(e),
        }

    rule_ids = [f.rule_id for f in findings]
    target_hit = fx["rule_id"] in rule_ids
    collateral = sorted(set(r for r in rule_ids if r != fx["rule_id"]))

    return {
        "rule_id": fx["rule_id"],
        "filename": fx["filename"],
        "parse_ok": True,
        "target_hit": target_hit,
        "target_count": rule_ids.count(fx["rule_id"]),
        "collateral": collateral,
        "total_findings": len(findings),
    }


def main():
    print(f"Verifying {len(FIXTURES)} fixtures against the linter...\n")
    rows = []
    for fx in FIXTURES:
        result = verify_one(fx)
        rows.append(result)

    # Summary table
    print(f"{'Rule':<13} {'Hit':<5} {'Parse':<7} {'Target#':<8} {'Collateral':<40}")
    print("-" * 80)
    passes = 0
    fails = 0
    for r in rows:
        if not r["parse_ok"]:
            print(f"{r['rule_id']:<13} ERR   PARSE    -        {r.get('error','?')[:40]}")
            fails += 1
            continue
        hit = "YES" if r["target_hit"] else "NO"
        if r["target_hit"]:
            passes += 1
        else:
            fails += 1
        collateral_str = ",".join(r["collateral"])[:38] or "(none)"
        print(f"{r['rule_id']:<13} {hit:<5} OK      {r['target_count']:<8} {collateral_str}")

    print()
    print(f"Passed: {passes}/{len(rows)}   Failed: {fails}/{len(rows)}")

    if fails > 0:
        print("\nFailures detail:")
        for r in rows:
            if r["parse_ok"] and not r["target_hit"]:
                print(f"  [{r['rule_id']}] {r['filename']}: target NOT hit. "
                      f"Rules that did fire: {','.join(r['collateral']) or '(none)'}")
            elif not r["parse_ok"]:
                print(f"  [{r['rule_id']}] {r['filename']}: PARSE ERROR: {r.get('error','?')}")


if __name__ == "__main__":
    main()
