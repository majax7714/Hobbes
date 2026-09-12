#include "../src/util.h"

int test_add_sums(void) {
    return add(2, 3) == 5;
}

int test_scale_is_positive(void) {
    return scale(3) > 0;
}

int helper_not_a_test(void) {
    return 0;
}
