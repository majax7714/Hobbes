#ifndef CCLANG_API_H
#define CCLANG_API_H

int lib_sum(int a, int b);
int lib_mul(int a, int b);
int helper(void);
int missing(void);
int get_one(void);

#define CALL_SUM(a, b) lib_sum((a), (b))
#define TWICE(x) ((x) + (x))
#define DEFINE_GETTER(name, val) \
    int name(void) { return (val); }

static inline int sq(int v) {
    return lib_mul(v, v);
}

#endif
