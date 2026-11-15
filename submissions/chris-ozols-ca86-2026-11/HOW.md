Construction: AI-assisted custom postoptimization by Chris Ozols of Bai XunDi's 87-row ternary strength-three array on 40 columns. The search combines row deletion, coordinated one-/two-cell tabu repair, and aligned three-column block operations with whole-pattern swaps. This submission claims the improved explicit array and upper bound, rather than novelty of the general postoptimization method.

The recorded successful branch used zero-based row and column indices:

1. Delete row 80 of the published CA(87;3,40,3). This leaves an 86-by-40 array with 31 missing interactions. The deletion and count were independently reproduced for this submission.
2. Run coordinated one-/two-cell tabu search with seed 1003. The recorded run reached three missing interactions at iteration 141,038.
3. Exploit the aligned column triples (c,c+13,c+26) for c = 0, 8, 10: (0,13,26), (8,21,34), and (10,23,36).
4. Repair coverage on those aligned triples, then search using whole-pattern swaps. The independent review records that completing aligned coverage temporarily left 15 defects elsewhere.
5. With seed 2026111401, the final stage reached one missing interaction at iteration 49 and zero at iteration 184. The independent review records byte-for-byte reproduction of this final stage from its saved three-defect checkpoint; it did not rerun the longer first stage.

The search chronology above is the supplied discovery record. The archived independent review corroborates the final-stage counts. The new checks for this submission verify the final matrix and the initial row-deletion count; they do not rerun the missing search implementation.

Built from: table/arrays/CA_87_3_40_3.txt of ca-tools, originally arrays/CA_87_3_40_3.txt in arrays_t3.zip of Bai XunDi's original dataset v1.0, DOI https://doi.org/10.5281/zenodo.23787055 (October 30, 2026). Parent SHA-256:

    677f089f0d797eec1fcbe9b6ffabe81f665b1405a83b06ee151ca59913504158

Bai's 40-column array is a computationally repaired extension of the Shokri-Moura 39-column q-plication construction at q=3. Credit for that underlying construction belongs to Kianoosh Shokri and Lucia Moura, *New families of strength-3 covering arrays using linear feedback shift register sequences*, Journal of Combinatorial Designs 33 (2025), 156-171, https://doi.org/10.1002/jcd.21963. The parent row's identifiers, deposit-bai2026 and lfsr-sm2025, are retained in builds_on. Chris Ozols is credited for the new 86-row improvement, with AI assistance acknowledged. The parent is CC BY 4.0; this submitted array is also released under CC BY 4.0, retaining the prior-construction credit.

Program: the original custom tabu/block-search implementation and checkpoints were packaged in an earlier search handoff, but were not included in the later Lean handoff. That earlier implementation was not located in the local Downloads or project archives checked for this submission, and is not in the linked result repository. The seeds and stage description above do not specify all move-selection, tabu, tie-breaking, and checkpoint details needed to regenerate the search independently. No claim is made that verify.sh runs that search or rebuilds the matrix from the 87-row parent.

The exact resulting matrix is available without rerunning the search at this immutable source:

https://github.com/cozuya/covering-array-86-3-40-3/blob/54ae2b69e0e3cee0abe389e621bf93b479d2b0d0/CA_86_3_40_3.txt

Its SHA-256 is:

    7dc7ab1e231dce3cde5cc1c6b35c4911f34145fd4dfe5d80f8ea26b235b27f8a

The source repository preserves the certificate, complete Lean 4.28.0 proof, and reproducible verification. To check the supplied matrix in a ca-tools checkout:

```sh
cc -O3 -pthread -o ca_verify ca_verify.c
./ca_verify submissions/chris-ozols-ca86-2026-11/CA_86_3_40_3.txt 3 3
python3 tools/check_submission.py submissions/chris-ozols-ca86-2026-11
```

To reproduce the formal verification:

```sh
git clone https://github.com/cozuya/covering-array-86-3-40-3.git
cd covering-array-86-3-40-3
git checkout 54ae2b69e0e3cee0abe389e621bf93b479d2b0d0
bash scripts/install-lean.sh
export PATH="$PWD/.tools/lean-4.28.0-linux/bin:$PATH"
./verify.sh
```

https://github.com/cozuya/covering-array-86-3-40-3/blob/54ae2b69e0e3cee0abe389e621bf93b479d2b0d0/REPRODUCE.md describes prerequisites and commands. The main declarations at this commit are CA86.ca86_covering and CA86.CAN_3_40_3_le_86. The covering checks use decide +kernel; the proof has no sorry, native_decide, or added axiom. The complete audit reports the standard Lean foundational axioms, with Classical.choice used for the least feasible row count. The independently checked numerical consequence is CAN(3,40,3) <= 86, not optimality.

The prior-art investigation, with cutoff November 14, 2026, returned LIKELY NOVEL within its documented scope and access limits. It is not a proof of worldwide priority. See https://github.com/cozuya/covering-array-86-3-40-3/blob/54ae2b69e0e3cee0abe389e621bf93b479d2b0d0/PRIOR_ART.md and https://github.com/cozuya/covering-array-86-3-40-3/blob/54ae2b69e0e3cee0abe389e621bf93b479d2b0d0/PROVENANCE.md. The public project page is https://cozuya.github.io/improvements/covering-array-86-3-40-3/.
