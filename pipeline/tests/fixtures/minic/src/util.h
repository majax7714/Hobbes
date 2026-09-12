#ifndef MINIC_UTIL_H
#define MINIC_UTIL_H

typedef struct {
    int (*add)(int, int);
} Adder;

int add(int a, int b);
int scale(int a);

#endif
