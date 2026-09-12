#include "util.h"

static int helper(int a) {
    return a + 1;
}

int add(int a, int b) {
    return helper(a) + helper(b);
}

int scale(int a) {
    Adder adder;
    adder.add = add;
    int (*fp)(int, int) = adder.add;
    return adder.add(a, a) + (*fp)(a, a);
}
