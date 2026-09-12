#ifndef MINIC_API_H
#define MINIC_API_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>

#define MINIC_CLAMP(x) ((x) < 0 ? 0 : (x))

typedef struct {
    int lo;
    int hi;
} MinicRange;

static inline int minic_twice(int a) { return a * 2; }

#ifdef __cplusplus
}
#endif

#endif
