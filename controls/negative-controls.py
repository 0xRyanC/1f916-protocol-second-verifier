#!/usr/bin/env python3
"""Negative controls for the witness branch: one-field mutations of the head-matching
countersignature line, run through verify.py and (optionally) the reference verify.mjs.

The manifest cases are all positive, so a verifier that always printed "witnessed"
would pass them. These rows check that the verifier can say no, and pin where the two
implementations disagree.

Usage (from the repo root; no network; fixtures are not modified, mutated copies go to a temp dir):
    python3 controls/negative-controls.py
    python3 controls/negative-controls.py --reference /path/to/1f916-ai/protocol   # needs node

Exit 0 when every observed verdict/exit equals controls/expected-controls.json for each
implementation that ran; 1 on any mismatch; 2 if a dependency is missing.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REG = "mpQPa0FjyynqoSg2Z9j91hRhb8WckxIpRGod43CQqLw"
WKEY = "BwLjer1DCxSErLiPIOG3fu0vlgmQierr2BC7f2k4TeI"
DOS = os.path.join(ROOT, "fixtures/dossier-citizen01-live-2026-09-23.json")
WIT = os.path.join(ROOT, "fixtures/witness-countersignatures-head-of-experiments-2026-09-23.jsonl")
VERDICTS = ["witness-unusable", "consistent-unwitnessed", "input-unusable", "unanchored", "witnessed", "diverged"]

def preflight(reference):
    try:
        import cryptography  # noqa: F401  (verify.py needs it; without it every case exits 2)
    except ImportError:
        sys.exit("missing dependency: pip install cryptography  (verify.py needs it for Ed25519)")
    if reference and not shutil.which("node"):
        sys.exit("--reference given but node is not on PATH")

def mutations(lines, i):
    def mut(f):
        o = json.loads(lines[i]); f(o); L = list(lines)
        L[i] = json.dumps(o, separators=(",", ":")); return "\n".join(L)
    def flip_b64(s): return s[:-2] + ("A" if s[-2] != "A" else "B") + s[-1]
    def flip_hex(s): return s[:-1] + ("0" if s[-1] != "0" else "1")
    def refusal_after_good():
        refused = json.loads(lines[i])
        refused["status"] = "refused-regression"
        refused.pop("witness_sig", None)
        return "\n".join(lines[:i + 1] + [json.dumps(refused, separators=(",", ":"))] + lines[i + 1:])
    return {
        "baseline": "\n".join(lines),
        "witness_public_key-flipped": mut(lambda o: o.__setitem__("witness_public_key", flip_b64(o["witness_public_key"]))),
        "status-refused-registry-key-epoch": mut(lambda o: o.__setitem__("status", "refused-registry-key-epoch")),
        "status-registry_signature_invalid": mut(lambda o: o.__setitem__("status", "registry_signature_invalid")),
        "registry-field-deleted": mut(lambda o: o.pop("registry")),
        "consistency-first-observation": mut(lambda o: o.__setitem__("consistency", "first observation")),
        "root-hex-flipped": mut(lambda o: o.__setitem__("root", flip_hex(o["root"]))),
        "status-pending": mut(lambda o: o.__setitem__("status", "pending")),
        "matching-line-deleted": "\n".join(lines[:i] + lines[i + 1:]),
        "refusal-appended-after-good": refusal_after_good(),
        "consistency-verified-from-19556": mut(lambda o: o.__setitem__("consistency", "verified from 19556")),
        "consistency-verified-from-99999": mut(lambda o: o.__setitem__("consistency", "verified from 99999")),
    }

def verdict_of(out):
    for ln in out.splitlines():
        low = ln.strip().lower()
        if low.startswith("verdict:"):
            v = low.split(":", 1)[1].strip().split()[0] if low.split(":", 1)[1].strip() else ""
            if v in VERDICTS: return v
    return "?"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", help="checkout of 1f916-ai/protocol (runs its verify.mjs too)")
    a = ap.parse_args()
    preflight(a.reference)
    expected = json.load(open(os.path.join(HERE, "expected-controls.json")))
    want = {r["name"]: r for r in expected["rows"]}
    raw = open(WIT, "rb").read()
    print(f"witness fixture sha256 {hashlib.sha256(raw).hexdigest()}")
    lines = raw.decode().split("\n")
    rows = json.load(open(DOS))["checkpoint"]
    rows = rows["checkpoints"] if "checkpoints" in rows else [rows]
    idx = [k for k, l in enumerate(lines) if l.strip()
           and any(json.loads(l).get("log") == r["log"] and json.loads(l).get("tree_size") == r["tree_size"] for r in rows)]
    if len(idx) != 1: sys.exit(f"expected exactly one head-matching line, found {idx}")
    i = idx[0]
    print(f"head-matching line {i + 1} of {sum(1 for l in lines if l.strip())}\n")
    ref_rev = None
    if a.reference:
        ref_rev = subprocess.run(["git", "-C", a.reference, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        print(f"reference verify.mjs @ {ref_rev or '(not a git checkout)'}")
    tmp = tempfile.mkdtemp(); bad = 0
    print(f"{'row':38s} {'verify.py':28s} {'verify.mjs' if a.reference else ''}")
    for name, body in mutations(lines, i).items():
        p = os.path.join(tmp, name + ".jsonl"); open(p, "w").write(body)
        args = ["--dossier", DOS, "--registry-key", REG, "--witness", p, "--witness-key", WKEY]
        r = subprocess.run([sys.executable, os.path.join(ROOT, "verify.py")] + args, capture_output=True, text=True)
        got_py = (verdict_of(r.stdout + r.stderr), r.returncode)
        w = want.get(name, {})
        exp_py = (w.get("verify_py", {}).get("verdict"), w.get("verify_py", {}).get("exit"))
        mark = "" if got_py == exp_py else f"  MISMATCH (expected {exp_py[0]}/{exp_py[1]})"
        bad += bool(mark)
        line = f"{name:38s} {got_py[0] + '/' + str(got_py[1]) + mark:28s}"
        if a.reference:
            r2 = subprocess.run(["node", os.path.join(a.reference, "verify.mjs")] + args, capture_output=True, text=True)
            got_ref = (verdict_of(r2.stdout + r2.stderr), r2.returncode)
            refexp = w.get("reference", {}).get(ref_rev) or w.get("reference", {}).get("default")
            m2 = "" if refexp is None or got_ref == (refexp["verdict"], refexp["exit"]) else f"  MISMATCH (expected {refexp['verdict']}/{refexp['exit']})"
            bad += bool(m2)
            line += f" {got_ref[0]}/{got_ref[1]}{m2}"
        print(line + f"   [{w.get('label', '?')}]")
    print(f"\n{'all rows match expected-controls.json' if not bad else f'{bad} mismatch(es)'}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
