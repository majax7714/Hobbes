#include "api.h"

struct ops {
    int (*fn)(int);
};

static int twin(int x) {
    return x + x;
}

int lib_sum(int a, int b) {
    return a + b;
}

int lib_mul(int a, int b) {
    return a * b;
}

DEFINE_GETTER(get_one, 1)

int lib_run(struct ops o, int (*cb)(int)) {
    int r = twin(1) + helper();
    r += missing();
    r += __builtin_abs(-2);
    r += o.fn(1) + cb(2);
    return r + sq(2);
}
