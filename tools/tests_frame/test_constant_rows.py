#!/usr/bin/env python3
"""Tests of tools/constant_rows_fast.c and tools/constant_rows_table.py (table/constant_rows.csv).

  - constant_rows_fast gives the same exact count as tools/constant_rows.c (the computation of
    cafast::maxconstant_c) on 200 random small arrays, with don't-care entries in some of them;
  - it finds all v rows of an array with v rows planted to be pairwise different everywhere, and its
    witness rows always pass the witness check;
  - with a zero time limit on a large array the basis is lower_bound, never exact;
  - the witness check of constant_rows_table.py rejects two rows that agree in a column and accepts a
    don't-care in the same column;
  - consistency.py check_constant_rows flags a count above v, a witness of the wrong length, an unknown
    basis, a hash of no VERIFIED row, and an array already counted in MANIFEST.csv.
No value of the live table is asserted. Usage: test_constant_rows.py (exit 1 on a failure)."""
import csv
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))
import constant_rows_table as crt  # noqa: E402

RESULTS = {"pass": 0, "fail": 0}


def check(cond, what):
    RESULTS["pass" if cond else "fail"] += 1
    print("%s  %s" % ("PASS" if cond else "FAIL", what), flush=True)
    return cond


def build(name):
    exe = os.path.join(tempfile.gettempdir(), "test_" + name)
    subprocess.run(["cc", "-O2", "-o", exe, os.path.join(REPO, "tools", name + ".c")], check=True)
    return exe


def write(path, arr):
    with open(path, "w") as f:
        for r in arr:
            f.write(" ".join(str(x) for x in r) + "\n")


def run(exe, path, v, *extra):
    out = subprocess.run([exe, path, str(v)] + [str(e) for e in extra], capture_output=True, text=True).stdout.split("\n")
    head = out[0].split()
    rows = [int(x) for x in out[1].replace("rows:", "").split()] if len(out) > 1 and out[1].startswith("rows:") else []
    return int(head[1]), head[-1], rows


def test_against_reference(fast, ref):
    rnd = random.Random(7)
    same = True
    witness = True
    for i in range(200):
        n, k, v = rnd.randint(5, 40), rnd.randint(2, 6), rnd.randint(2, 6)
        arr = [[rnd.randrange(v) for _ in range(k)] for _ in range(n)]
        arr[0] = [0] * k
        arr[-1] = [v - 1] * k             # both symbols present, so 0..v-1 is read as 0-based
        if i % 4 == 0:
            for r in arr[1:-1]:
                if rnd.random() < 0.3:
                    r[rnd.randrange(k)] = "-"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt")
            write(p, arr)
            c1, b1, rows = run(fast, p, v, 30)
            o = subprocess.run([ref, p, str(v)], capture_output=True, text=True).stdout.split()
            c2 = int(o[1])
            ok, _ = crt.witness_ok(p, rows)
        same &= (c1 == c2 and b1 == "exact")
        witness &= ok and len(rows) == c1
    check(same, "constant_rows_fast equals tools/constant_rows.c (exact) on 200 random arrays")
    check(witness, "its witness rows always differ pairwise in every column")


def test_planted(fast):
    rnd = random.Random(11)
    v, k, n = 7, 12, 3000
    arr = [[rnd.randrange(v) for _ in range(k)] for _ in range(n)]
    perm = [rnd.sample(range(v), v) for _ in range(k)]
    pos = rnd.sample(range(n), v)
    for s, r in enumerate(pos):
        arr[r] = [perm[c][s] for c in range(k)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.txt")
        write(p, arr)
        c, b, rows = run(fast, p, v, 60)
        check(c == v and b == "exact" and crt.witness_ok(p, rows)[0],
              "v planted rows pairwise different everywhere are found: count v, exact")
        c, b, rows = run(fast, p, v, 0, 1, 10)
        check(b == "lower_bound" and crt.witness_ok(p, rows)[0],
              "random roots under a zero time limit: lower_bound with a valid witness")


def test_witness_check():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.txt")
        write(p, [[0, 1, 2], [1, 2, 0], [0, 0, 1], ["-", 0, 1]])
        check(crt.witness_ok(p, [1, 2])[0], "rows 1, 2 differ in every column: accepted")
        check(not crt.witness_ok(p, [1, 3])[0], "rows 1, 3 agree in column 1: rejected")
        check(crt.witness_ok(p, [2, 4])[0], "a don't-care never counts as agreeing")
        check(not crt.witness_ok(p, [1, 9])[0], "a row beyond the array: rejected")


def test_consistency():
    import consistency as cc
    sha_ok, sha_man, sha_none = "1" * 64, "2" * 64, "3" * 64
    rows = [{"t": "2", "v": "3", "k": "4", "N": "9", "tier": "VERIFIED", "array_sha256": sha_ok},
            {"t": "2", "v": "3", "k": "4", "N": "9", "tier": "VERIFIED", "array_sha256": sha_man}]
    man = [{"sha256": sha_man, "constant_rows": "3"}]
    cases = [
        ([sha_ok, 3, "exact", "1 2 3", "constant_rows_fast", "2026-11-14"], 0, "a valid line"),
        ([sha_ok, 4, "exact", "1 2 3 4", "constant_rows_fast", "2026-11-14"], 1, "a count above v"),
        ([sha_ok, 2, "exact", "1 2 3", "constant_rows_fast", "2026-11-14"], 1, "a witness of the wrong length"),
        ([sha_ok, 2, "maybe", "1 2", "constant_rows_fast", "2026-11-14"], 1, "an unknown basis"),
        ([sha_ok, 2, "exact", "1 10", "constant_rows_fast", "2026-11-14"], 1, "a witness row above N"),
        ([sha_none, 2, "exact", "1 2", "constant_rows_fast", "2026-11-14"], 1, "the hash of no VERIFIED row"),
        ([sha_man, 2, "exact", "1 2", "constant_rows_fast", "2026-11-14"], 1, "an array counted in MANIFEST.csv"),
    ]
    old = cc.CONSTANT_ROWS
    for line, want, what in cases:
        with tempfile.TemporaryDirectory() as d:
            cc.CONSTANT_ROWS = os.path.join(d, "constant_rows.csv")
            with open(cc.CONSTANT_ROWS, "w", newline="") as f:
                w = csv.writer(f, lineterminator="\n")
                w.writerow(cc.CONSTANT_ROWS_HEADER)
                w.writerow(line)
            del cc.problems[:]
            cc.check_constant_rows(rows, man)
            check(len(cc.problems) == want, "consistency: %s gives %d problem(s)" % (what, want))
    cc.CONSTANT_ROWS = old
    del cc.problems[:]


def main():
    fast, ref = build("constant_rows_fast"), build("constant_rows")
    test_against_reference(fast, ref)
    test_planted(fast)
    test_witness_check()
    test_consistency()
    print("%d passed, %d failed" % (RESULTS["pass"], RESULTS["fail"]))
    return 1 if RESULTS["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
