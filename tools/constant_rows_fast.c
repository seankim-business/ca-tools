/* constant_rows_fast.c - the number of rows of a covering array that can be made constant by
   permuting symbols within columns, for arrays too large for tools/constant_rows.c.

   Two rows can both be made constant exactly when they differ in every column in which both are
   non-missing, so the answer is the largest clique of that graph, capped at v (with don't-care entries a
   clique can be larger than v, but only v symbols exist). tools/constant_rows.c
   builds the whole graph and searches it without a good bound; this program

     - finds the rows compatible with a root row from per-column symbol bitsets (no N x N graph),
     - searches the neighbourhood of each root by branch and bound with a greedy colouring bound
       (Tomita, San Segundo bitset form), and stops as soon as v rows are found (the maximum);
     - under a time limit, reports the best set found. The count is "exact" only if the search
       finished (every root tried, no neighbourhood sampled, no time-out) or v rows were found;
       otherwise it is a "lower_bound" (a set of that many rows can be made constant).

   Input conventions are those of ca_verify.c and constant_rows.c (symbols 0..v-1 or 1..v, don't
   care NA, '-', '*', 'x', 'X', -1; v at most 127). Usage: constant_rows_fast FILE v [seconds [seed [nexact]]]
   Every root row is tried in file order when N <= nexact (default 40000), else in a random order (seed).
   Output: "constant_rows C of N rows, k columns, v symbols, basis exact|lower_bound" then
   "rows: i1 i2 ..." (1-based). Exit 0, or 2 on a read error. The rows printed are a witness: they differ pairwise in every
   column where both are non-missing, so a count is always a true lower bound (tools/constant_rows_table.py
   verify checks the witnesses of table/constant_rows.csv).
   Build: cc -O2 -o constant_rows_fast constant_rows_fast.c  (optional: -march=native) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <strings.h>

#define NA_CELL (-1)
typedef uint64_t u64;
static int N, K, V;
static signed char *D;
static u64 *colsym;         /* (c * V + s) * W : rows with symbol s in column c */
static int W;               /* words per full-length bitset */
static double deadline; static int timed_out = 0, sampled = 0; static unsigned long ticks = 0;
static int best_total = 0; static int *best_rows; static int cur_n; static int *cur_rows;
static int *Pmap;           /* local index -> row */
static u64 *adj; static int LW;   /* local adjacency, LW words per vertex */

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + 1e-9 * t.tv_nsec; }

static int read_array(const char *path, int v) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 0; }
    size_t cap = 1 << 16, n = 0; signed char *buf = malloc(cap);
    int cols = -1, col = 0, rows = 0, minv = 1 << 30, maxv = -1;
    char tok[64]; int tl = 0; int c; int any = 0;
    for (;;) {
        c = fgetc(f);
        int sep = (c == ' ' || c == '\t' || c == ',' || c == '\r' || c == '\n' || c == EOF);
        if (!sep) { if (tl >= 63) { fprintf(stderr, "token too long\n"); fclose(f); free(buf); return 0; } tok[tl++] = (char)c; continue; }
        if (tl > 0) {
            tok[tl] = 0; int val;
            if (!strcmp(tok, "-") || !strcmp(tok, "*") || !strcmp(tok, "x") || !strcmp(tok, "X") ||
                !strcmp(tok, "-1") || !strcasecmp(tok, "NA")) val = NA_CELL;
            else { char *e; long x = strtol(tok, &e, 10); if (*e) { fprintf(stderr, "bad token %s\n", tok); fclose(f); free(buf); return 0; }
                   val = (int)x; if (val < minv) minv = val; if (val > maxv) maxv = val; }
            if (n == cap) { cap *= 2; buf = realloc(buf, cap); }
            buf[n++] = (signed char)val; col++; any = 1; tl = 0;
        }
        if (c == '\n' || c == EOF) {
            if (any) { if (cols < 0) cols = col; else if (col != cols) { fprintf(stderr, "line %d has %d entries, expected %d\n", rows + 1, col, cols); fclose(f); free(buf); return 0; }
                       rows++; }
            col = 0; any = 0;
            if (c == EOF) break;
        }
    }
    fclose(f);
    if (rows == 0 || cols <= 0) { fprintf(stderr, "empty array\n"); free(buf); return 0; }
    for (int i = 0; i < rows; i++) { int allna = 1; for (int c2 = 0; c2 < cols; c2++) if (buf[(size_t)i * cols + c2] != NA_CELL) { allna = 0; break; }
        if (allna) { fprintf(stderr, "row %d consists only of don't-care entries\n", i + 1); free(buf); return 0; } }
    int shift = (minv == 1 && maxv == v) ? 1 : 0;
    if (maxv - shift > v - 1 || minv - shift < 0) { fprintf(stderr, "symbols outside 0..%d\n", v - 1); free(buf); return 0; }
    N = rows; K = cols; V = v; D = buf;
    if (shift) for (size_t i = 0; i < n; i++) if (D[i] != NA_CELL) D[i] -= 1;
    return 1;
}

static int disjoint(int i, int j) {
    const signed char *a = D + (size_t)i * K, *b = D + (size_t)j * K;
    for (int c = 0; c < K; c++) if (a[c] != NA_CELL && b[c] != NA_CELL && a[c] == b[c]) return 0;
    return 1;
}

static void record(void) {
    if (cur_n > best_total) { best_total = cur_n; memcpy(best_rows, cur_rows, sizeof(int) * cur_n); }
}

/* Branch and bound on the local graph (vertices 0..m-1, adjacency adj, LW words each). P is a bitset. */
static void expand(u64 *P, int base) {
    if (timed_out || best_total >= V) return;
    int n = 0; int mv = LW * 64;
    int *order = malloc(sizeof(int) * (size_t)mv), *color = malloc(sizeof(int) * (size_t)mv);
    u64 *Q = malloc(sizeof(u64) * LW), *Qc = malloc(sizeof(u64) * LW);
    memcpy(Q, P, sizeof(u64) * LW);
    int kcol = 0;
    for (;;) {
        int any = 0; for (int w = 0; w < LW; w++) if (Q[w]) { any = 1; break; }
        if (!any) break;
        kcol++; memcpy(Qc, Q, sizeof(u64) * LW);
        for (;;) {
            int w = 0; while (w < LW && !Qc[w]) w++;
            if (w == LW) break;
            int v = w * 64 + __builtin_ctzll(Qc[w]);
            Q[w] &= ~(1ULL << (v & 63)); Qc[w] &= ~(1ULL << (v & 63));
            const u64 *av = adj + (size_t)v * LW;
            for (int x = w; x < LW; x++) Qc[x] &= ~av[x];   /* keep non-neighbours (independent colour class) */
            order[n] = v; color[n] = kcol; n++;
        }
    }
    u64 *NP = malloc(sizeof(u64) * LW);
    for (int i = n - 1; i >= 0; i--) {
        if (base + color[i] <= best_total) break;
        if ((++ticks & 0xFFF) == 0 && now() > deadline) { timed_out = 1; break; }
        int v = order[i];
        cur_rows[cur_n++] = Pmap[v];
        if (cur_n >= V) { record(); cur_n--; break; }   /* v rows: the maximum (with don't-care entries a
                                                           larger clique exists but only v symbols do) */
        const u64 *av = adj + (size_t)v * LW; int nonempty = 0;
        for (int w = 0; w < LW; w++) { NP[w] = P[w] & av[w]; if (NP[w]) nonempty = 1; }
        if (nonempty) expand(NP, base + 1); else record();
        cur_n--;
        if (timed_out || best_total >= V) break;
        P[v >> 6] &= ~(1ULL << (v & 63));
    }
    free(NP); free(order); free(color); free(Q); free(Qc);
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: constant_rows_fast FILE v [seconds [seed [nexact]]]\n"); return 2; }
    int v = atoi(argv[2]); double secs = argc > 3 ? atof(argv[3]) : 600; unsigned seed = argc > 4 ? (unsigned)atoi(argv[4]) : 1;
    long nexact = argc > 5 ? atol(argv[5]) : 40000;
    if (v < 2 || v > 127 || !read_array(argv[1], v)) return 2;
    deadline = now() + secs; srand(seed);
    W = (N + 63) / 64;
    colsym = calloc((size_t)K * V * W, sizeof(u64));
    for (int i = 0; i < N; i++) for (int c = 0; c < K; c++) { int s = D[(size_t)i * K + c]; if (s != NA_CELL) colsym[((size_t)c * V + s) * W + (i >> 6)] |= 1ULL << (i & 63); }
    best_rows = malloc(sizeof(int) * (V + 1)); cur_rows = malloc(sizeof(int) * (V + 2));
    const int MMAX = 12000;
    int sequential = N <= nexact;
    int *perm = malloc(sizeof(int) * N); for (int i = 0; i < N; i++) perm[i] = i;
    if (!sequential) for (int i = N - 1; i > 0; i--) { int j = rand() % (i + 1); int t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    u64 *comp = malloc(sizeof(u64) * W);
    int roots_done = 0;
    for (int ri = 0; ri < N && best_total < V; ri++) {
        if (now() > deadline) { timed_out = 1; break; }
        int r = perm[ri];
        for (int w = 0; w < W; w++) comp[w] = ~0ULL;
        if (N & 63) comp[W - 1] = (1ULL << (N & 63)) - 1;
        for (int c = 0; c < K; c++) { int s = D[(size_t)r * K + c]; if (s == NA_CELL) continue;
            const u64 *cs = colsym + ((size_t)c * V + s) * W; for (int w = 0; w < W; w++) comp[w] &= ~cs[w]; }
        comp[r >> 6] &= ~(1ULL << (r & 63));
        if (sequential) { for (int w = 0; w < (r >> 6); w++) comp[w] = 0; comp[r >> 6] &= ~((2ULL << (r & 63)) - 1); }
        int m = 0; for (int w = 0; w < W; w++) m += __builtin_popcountll(comp[w]);
        roots_done++;
        if (1 + m <= best_total) continue;
        if (best_total < 1) { best_total = 1; best_rows[0] = r; }
        Pmap = malloc(sizeof(int) * (m > 0 ? m : 1)); int mm = 0;
        for (int w = 0; w < W; w++) { u64 x = comp[w]; while (x) { Pmap[mm++] = w * 64 + __builtin_ctzll(x); x &= x - 1; } }
        if (mm > MMAX) { /* keep a random sample: the result is then only a lower bound */
            for (int i = mm - 1; i > 0; i--) { int j = rand() % (i + 1); int t = Pmap[i]; Pmap[i] = Pmap[j]; Pmap[j] = t; }
            mm = MMAX; sampled = 1;
            /* sorted order is not needed */
        }
        LW = (mm + 63) / 64;
        adj = calloc((size_t)mm * LW, sizeof(u64));
        for (int i = 0; i < mm; i++) for (int j = i + 1; j < mm; j++) if (disjoint(Pmap[i], Pmap[j])) {
            adj[(size_t)i * LW + (j >> 6)] |= 1ULL << (j & 63); adj[(size_t)j * LW + (i >> 6)] |= 1ULL << (i & 63); }
        u64 *P = malloc(sizeof(u64) * LW); for (int w = 0; w < LW; w++) P[w] = ~0ULL; if (mm & 63) P[LW - 1] = (1ULL << (mm & 63)) - 1;
        cur_n = 0; cur_rows[cur_n++] = r;
        int nonempty = mm > 0;
        if (nonempty) expand(P, 1); else record();
        free(P); free(adj); free(Pmap);
        if (timed_out) break;
    }
    int exact = (best_total >= V) || (sequential && !timed_out && sampled == 0 && roots_done == N);
    printf("constant_rows %d of %d rows, %d columns, %d symbols, basis %s\n", best_total, N, K, V, exact ? "exact" : "lower_bound");
    printf("rows:"); for (int i = 0; i < best_total; i++) printf(" %d", best_rows[i] + 1); printf("\n");
    return 0;
}
