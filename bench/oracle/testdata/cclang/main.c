#include "api.h"

static int choose(void) {
    return 1;
}

#include "pick.h"

int helper(void) {
    return 10;
}

static int apply(int (*f)(int, int)) {
    return (*f)(1, 2);
}

int main(void) {
    int r = CALL_SUM(1, 2);
    r += TWICE(lib_sum(3, 4));
    r += sq(3) + get_one();
    r += lib_mul
        (5, 6);
    r += helper() + pick();
    r += apply(lib_sum) + (lib_sum)(7, 8);
    return r;
}
