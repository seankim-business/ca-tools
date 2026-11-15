#!/usr/bin/env python3
"""constant_rows_table - the constant-row counts of table/constant_rows.csv: compute, record, verify.

table/constant_rows.csv records the number of constant rows (the largest set of rows that can all be made
constant by permuting symbols within columns, at most v) for arrays whose count is not in
table/MANIFEST.csv: arrays rebuilt from a construction certificate (table/constructions), from a covering
perfect hash family (table/certificates), kept in a deposit (table/EXTERNAL.csv), and stored arrays whose
MANIFEST count is empty. tools/build_frame.py reads it by array_sha256 into the constant_rows and
constant_rows_basis columns of table/ca_frame.csv. Columns:

  array_sha256   the canonical sha256 of the array (the array_sha256 of its VERIFIED table row)
  constant_rows  the count
  basis          exact: the search of tools/constant_rows_fast.c tried every root row and finished, or
                 found v rows (the maximum); lower_bound: a set of that many rows was found, no proof that
                 none larger exists
  witness_rows   the rows found, 1-based and space separated, in the array as its frame get_ref builds it.
                 They differ pairwise in every column where both are non-missing, so the count is always at
                 least a true lower bound; "verify" below checks that on the rebuilt array
  method         the program that found them (constant_rows_fast)
  computed       the date

Usage:
  constant_rows_table.py count ARRAY.txt v SHA256 [--seconds S] [--nexact N]
        run tools/constant_rows_fast on ARRAY.txt (plain or .gz) and print the CSV line for it
  constant_rows_table.py verify [--table-dir DIR] [--max-cells C] [SHA256 ...]
        rebuild each listed array (all when none is named) from its frame get_ref (file, construction
        certificate, CPHF certificate with fuse2 steps; deposits are skipped) and check its witness rows.
        Exit 1 on a failed witness.
Standard library only; count compiles tools/constant_rows_fast.c with cc on first use.
"""
import csv
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = ["array_sha256", "constant_rows", "basis", "witness_rows", "method", "computed"]
NA = {"-", "*", "x", "X", "-1", "NA", "na"}


def binary(name, src, extra=()):
    exe = os.path.join(tempfile.gettempdir(), "ca_tools_" + name)
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        subprocess.run(["cc", "-O2", "-o", exe, src] + list(extra), check=True)
    return exe


def plain(path, tmpdir):
    if not path.endswith(".gz"):
        return path
    out = os.path.join(tmpdir, "array.txt")
    with gzip.open(path, "rb") as a, open(out, "wb") as b:
        shutil.copyfileobj(a, b)
    return out


def count(argv):
    secs = argv[argv.index("--seconds") + 1] if "--seconds" in argv else "600"
    nexact = argv[argv.index("--nexact") + 1] if "--nexact" in argv else "40000"
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    path, v, sha = pos[:3]
    exe = binary("constant_rows_fast", os.path.join(REPO, "tools", "constant_rows_fast.c"))
    with tempfile.TemporaryDirectory() as d:
        out = subprocess.run([exe, plain(path, d), v, secs, "1", nexact], capture_output=True, text=True)
    lines = out.stdout.splitlines()
    if out.returncode or len(lines) < 2:
        sys.exit("constant_rows_fast failed: %s" % out.stderr.strip())
    m = re.match(r"^constant_rows (\d+) of .* basis (exact|lower_bound)$", lines[0])
    wit = lines[1].replace("rows:", "").strip()
    import datetime
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow([sha, m.group(1), m.group(2), wit, "constant_rows_fast", datetime.date.today().isoformat()])
    return 0


def witness_ok(path, rows):
    """True if the given 1-based rows of the array at path differ pairwise in every column where both
    are non-missing; reads the file once and keeps only those rows"""
    want = set(rows)
    got = {}
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            vals = line.replace(",", " ").split()
            if not vals:
                continue
            n += 1
            if n in want:
                got[n] = vals
    if set(got) != want:
        return False, "witness row beyond the %d rows of the array" % n
    rs = [got[r] for r in rows]
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            if len(a) != len(b):
                return False, "rows %d and %d differ in length" % (rows[i], rows[j])
            for x, y in zip(a, b):
                if x == y and x not in NA:
                    return False, "rows %d and %d agree in a column" % (rows[i], rows[j])
    return True, "%d rows, pairwise different in every column" % len(rows)


def rebuild(fr, tmp, table_dir):
    """the path of the array the frame line's get_ref builds, or None with a reason"""
    get, ref = fr["get"], fr["get_ref"]
    if get == "file":
        return plain(os.path.join(REPO, ref), tmp), ""
    if get == "construction":
        cert = ref.split()[2]
        out = os.path.join(tmp, "array.txt")
        p = subprocess.run([sys.executable, os.path.join(REPO, "tools", "construction_cert.py"),
                            os.path.join(REPO, cert), "--write", out, "--quiet", "--table-dir", table_dir],
                           capture_output=True, text=True)
        return (out, "") if "CERTIFICATE VALID" in p.stdout else (None, "certificate check failed")
    if get == "certificate":
        m = re.match(r"^tools/cphf/cphfcheck (\S+) (\d+) (\d+) expand CA\.txt( affine)?(.*)$", ref)
        if not m:
            return None, "unrecognised get_ref"
        steps = re.findall(r"then (fuse2 \d+|fuse \d+>\d+)", m.group(5))
        if any(not s.startswith("fuse2") for s in steps):
            return None, "fuse a>b steps are not rebuilt here"
        chk = binary("cphfcheck", os.path.join(REPO, "tools", "cphf", "cphfcheck.c"), ["-pthread", "-lm"])
        cur = os.path.join(tmp, "expanded.txt")
        cmd = [chk, os.path.join(REPO, m.group(1)), m.group(2), m.group(3), "expand", cur] + (["affine"] if m.group(4) else [])
        subprocess.run(cmd, check=True, capture_output=True)
        fuse = binary("fuse2", os.path.join(REPO, "tools", "cphf", "fuse2.c"))
        for i, s in enumerate(steps):
            nxt = os.path.join(tmp, "fused%d.txt" % i)
            with open(cur) as inp:
                subprocess.run([fuse, s.split()[1], m.group(2), "0", "1", nxt], stdin=inp, check=True, capture_output=True)
            os.remove(cur)
            cur = nxt
        return cur, ""
    return None, "get %s is not rebuilt here" % get


def verify(argv):
    table_dir = argv[argv.index("--table-dir") + 1] if "--table-dir" in argv else os.path.join(REPO, "table")
    max_cells = float(argv[argv.index("--max-cells") + 1]) if "--max-cells" in argv else float("inf")
    only = {a for a in argv if re.match(r"^[0-9a-f]{64}$", a)}
    recs = list(csv.DictReader(open(os.path.join(table_dir, "constant_rows.csv"), newline="", encoding="utf-8")))
    rows = list(csv.DictReader(open(os.path.join(table_dir, "ca_table.csv"), newline="", encoding="utf-8")))
    sha_row = {}
    for r in rows:
        if r["tier"] == "VERIFIED" and r["array_sha256"]:
            sha_row.setdefault(r["array_sha256"], r)
    # the get_ref of an array, worked out as the frame does (tools/build_frame.py)
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import build_frame
    ctx = build_frame.Context(table_dir)
    bad = 0
    for rec in recs:
        sha = rec["array_sha256"]
        if only and sha not in only:
            continue
        r = sha_row.get(sha)
        if r is None:
            print("FAIL %s: no VERIFIED row" % sha[:12]); bad += 1
            continue
        if int(r["N"]) * int(r["k"]) > max_cells:
            print("SKIP %s: CA(%s;%s,%s,%s) above --max-cells" % (sha[:12], r["N"], r["t"], r["k"], r["v"]))
            continue
        get, ref = ctx.get_of(r)
        with tempfile.TemporaryDirectory() as tmp:
            path, why = rebuild({"get": get, "get_ref": ref}, tmp, table_dir)
            if path is None:
                print("SKIP %s: %s" % (sha[:12], why))
                continue
            wit = [int(x) for x in rec["witness_rows"].split()]
            ok, msg = witness_ok(path, wit)
        ok = ok and len(wit) == int(rec["constant_rows"])
        print("%s %s: CA(%s;%s,%s,%s) %s %s, %s" % ("PASS" if ok else "FAIL", sha[:12], r["N"], r["t"], r["k"],
              r["v"], rec["constant_rows"], rec["basis"], msg))
        bad += 0 if ok else 1
    print("constant_rows_table verify: %d failed" % bad)
    return 1 if bad else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["count"]:
        return count(argv[1:])
    if argv[:1] == ["verify"]:
        return verify(argv[1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
