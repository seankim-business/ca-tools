## Submission

cafast 0.1.1, an update of 0.1.0 (on CRAN).

Changes (see NEWS.md):

* New function `CA_to_PCA_c()`, a compiled and exact version of the
  partition step of `CAs::CA_to_PCA()` for strength 2 arrays.
* `maxconstant_c()` counts a repeated constant row once. Two cases in
  which duplicated constant rows gave a wrong answer are fixed, with
  tests.

## Test environments

* local: Ubuntu 24.04 (container), x86_64-pc-linux-gnu, R 4.3.3
  (2024-02-29), gcc 13.3.0, `R CMD check --as-cran` on the tarball,
  2026-11-14: Status 2 NOTEs.

## R CMD check results

0 errors | 0 warnings | 2 notes

      checking compilation flags used ... NOTE
      Compilation used the following non-portable flag(s):
        '-mno-omit-leaf-frame-pointer'

The flag comes from the CFLAGS of the Ubuntu build of R on the test
machine, not from the package, which has no Makevars.

      checking HTML version of manual ... NOTE
      Skipping checking HTML validation: no command 'tidy' found
      Skipping checking math rendering: package 'V8' unavailable

Local tooling only. It does not arise on CRAN.
