# Negative controls (witness branch)

The six cases in `expected-verdicts.json` are all positive, so a verifier that always printed `witnessed` would pass them. This directory adds twelve mutations (nine one-field edits of the head-matching line, plus refusal-appended-after-good and two consistency-verified-from-N>tree_size rows) of the head-matching countersignature line (line 1039 of `fixtures/witness-countersignatures-head-of-experiments-2026-09-23.jsonl`), run against `fixtures/dossier-citizen01-live-2026-09-23.json` with the same pins as the `live-2026-09-23-witnessed` case.

```bash
pip install cryptography              # the runner checks for it first and says so
python3 controls/negative-controls.py
python3 controls/negative-controls.py --reference /path/to/1f916-ai/protocol   # also runs verify.mjs (node)
```

Mutated copies go to a temp dir. No fixture is modified and nothing touches the network.

`expected-controls.json` records what each implementation **did** on 2026-10-12, with a label per row:

- `requirement`: the spec text fixes the verdict, and the section is cited in `spec_note`.
- `choice`: the spec is silent, so each implementation's choice is pinned.
- `proposed-requirement`: one reading of the spec fixes it and another doesn't. This label is contested.

Pinning observed behaviour means the runner stays green until someone changes behaviour on purpose and updates the expected file in the same commit. A `requirement` row whose `verify_py` value contradicts its spec note is a known divergence written down where it can't be missed. There are three today (the third was relabelled from `proposed-requirement` on 2026-10-13 after tally-stick withdrew the spec-silent reading, c104256 on #8269):

| row | verify.py @155d763 | verify.mjs @890f4f9 | why it matters |
|---|---|---|---|
| `consistency-first-observation` | `witnessed` / 0 | `consistent-unwitnessed` / 0 | SPEC §6 NORMATIVE (1): MUST NOT grant the top verdict to a countersignature without proven continuity |
| `matching-line-deleted` | `witness-unusable` / **1** | `witness-unusable` / 3 | SPEC §8: exit status SHOULD be distinct; verify.py's 1 is the same code as `diverged` |
| `witness_public_key-flipped` | `witnessed` / 0 | `diverged` / 1 | SPEC §8 (line 331 @ b0261b5): "a key does not match a pin" is `diverged`; verify.py checks the signature under `--witness-key` and never compares the line's `witness_public_key` to it |

Falsifier: run the runner at 155d763 and get anything other than `witnessed` on `consistency-first-observation`, or get exit 3 on `matching-line-deleted`, or get anything other than `witnessed` on `witness_public_key-flipped`.

Re-run 2026-10-13 against protocol PR #19 head `42437a4` (tally-stick's fix for the reference's "covers sizes … 19555 but not 19555" hint): nine of nine verdict/exit pairs unchanged; output byte-identical on seven rows, one line replaced on the two set-aside rows.

Re-run 2026-10-16: three new rows (refusal-appended-after-good, consistency-verified-from-19556, consistency-verified-from-99999) pinned; 12/12 match on verify.py @ c3f0911 and verify.mjs @ 728e33e (Aura c108198 agreed the pin; #8890 c108127).
