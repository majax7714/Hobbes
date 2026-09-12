#include "util.h"

static int helper(int a) {
    return a * 2;
}

int square(int a) {
    return helper(a) * helper(a);
}

int scale(int a) {
    return a * 10;
}
