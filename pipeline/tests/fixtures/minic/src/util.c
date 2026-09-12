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

#if defined(_WIN32)
static char *strcasestr(const char *haystack, const char *needle) {
    (void)haystack;
    (void)needle;
    return NULL;
}
#endif

#define _GNU_SOURCE
#include <string.h>

int mentions_add(const char *name) {
    return strcasestr(name, "add") != NULL;
}
