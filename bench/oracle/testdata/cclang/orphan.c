#include "api.h"

/* No Makefile target compiles this file: its sites are not-loaded. */
int orphan(void) {
    return lib_sum(1, 1);
}
