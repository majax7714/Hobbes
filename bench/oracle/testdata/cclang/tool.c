#include "api.h"

static int choose(void) {
    return 2;
}

#include "pick.h"

int helper(void) {
    return 20;
}

int main(void) {
    return pick() + helper() + lib_sum(1, 2);
}
