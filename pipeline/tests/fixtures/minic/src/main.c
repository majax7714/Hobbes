#include "util.h"
#include <minic/config.h>
#include <stdio.h>

static void run(int (*add)(int, int)) {
    printf("%d\n", add(2, 3));
}

int main(void) {
    int sum = add(2, 3);
    int big = MINIC_MAX(sum, MINIC_VERSION);
    printf("sum=%d big=%d\n", sum, big);
    run(add);
    return 0;
}

#include <minic/api.h>

static void extra(void) {
    int clamped = MINIC_CLAMP(-5);
    int doubled = minic_twice(clamped);
    (void)clamped;
    (void)doubled;
}
