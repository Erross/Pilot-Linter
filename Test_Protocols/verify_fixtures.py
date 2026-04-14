"""
Verify every fixture triggers its target rule.
Also report any unexpected cross-triggered rules so we can see what
collateral findings each fixture produces.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ppxml_linter
from generate_fixtures import FIXTURES, NEGATIVE_FIXTURES

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


def verify_one_negative(fx):
    """For negative fixtures: the target rule must NOT appear in findings."""
    path = os.path.join(FIXTURES_DIR, fx["filename"])
    try:
        parser, findings = ppxml_linter.run_lint(path)
    except Exception as e:
        return {
            "rule_id": fx["rule_id"],
            "filename": fx["filename"],
            "parse_ok": False,
            "target_absent": False,
            "all_rules": [],
            "error": str(e),
        }

    rule_ids = [f.rule_id for f in findings]
    target_absent = fx["rule_id"] not in rule_ids
    collateral = sorted(set(rule_ids))   # all rules that fired (there's no "expected" one)

    return {
        "rule_id": fx["rule_id"],
        "filename": fx["filename"],
        "parse_ok": True,
        "target_absent": target_absent,
        "collateral": collateral,
        "total_findings": len(findings),
    }


def main():
    print(f"Verifying {len(FIXTURES)} positive + {len(NEGATIVE_FIXTURES)} negative fixtures...\n")

    # ---- positive fixtures ----
    rows = []
    for fx in FIXTURES:
        result = verify_one(fx)
        rows.append(result)

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
    print(f"Positive passed: {passes}/{len(rows)}   Failed: {fails}/{len(rows)}")

    if fails > 0:
        print("\nPositive failures detail:")
        for r in rows:
            if r["parse_ok"] and not r["target_hit"]:
                print(f"  [{r['rule_id']}] {r['filename']}: target NOT hit. "
                      f"Rules that did fire: {','.join(r['collateral']) or '(none)'}")
            elif not r["parse_ok"]:
                print(f"  [{r['rule_id']}] {r['filename']}: PARSE ERROR: {r.get('error','?')}")

    # ---- negative fixtures ----
    if NEGATIVE_FIXTURES:
        print(f"\n{'Rule':<13} {'Absent':<7} {'Parse':<7} {'Collateral':<40}")
        print("-" * 80)
        neg_passes = 0
        neg_fails = 0
        neg_rows = []
        for fx in NEGATIVE_FIXTURES:
            r = verify_one_negative(fx)
            neg_rows.append(r)
            if not r["parse_ok"]:
                print(f"{r['rule_id']:<13} ERR    PARSE   {r.get('error','?')[:40]}")
                neg_fails += 1
                continue
            absent = "YES" if r["target_absent"] else "NO (FAIL)"
            if r["target_absent"]:
                neg_passes += 1
            else:
                neg_fails += 1
            collateral_str = ",".join(r["collateral"])[:38] or "(none)"
            print(f"{r['rule_id']:<13} {absent:<7} OK      {collateral_str}")

        print()
        print(f"Negative passed: {neg_passes}/{len(neg_rows)}   Failed: {neg_fails}/{len(neg_rows)}")

        if neg_fails > 0:
            print("\nNegative failures detail:")
            for r in neg_rows:
                if r["parse_ok"] and not r["target_absent"]:
                    print(f"  [{r['rule_id']}] {r['filename']}: target rule fired (should be suppressed). "
                          f"All rules: {','.join(r['collateral']) or '(none)'}")
                elif not r["parse_ok"]:
                    print(f"  [{r['rule_id']}] {r['filename']}: PARSE ERROR: {r.get('error','?')}")

        fails += neg_fails

    print()
    total = len(rows) + len(NEGATIVE_FIXTURES)
    total_pass = passes + (neg_passes if NEGATIVE_FIXTURES else 0)
    print(f"Passed: {total_pass}/{total}   Failed: {fails}/{total}")


if __name__ == "__main__":
    main()
