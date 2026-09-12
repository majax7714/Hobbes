#include <byteswap.h>
#define PASTE(a, b) a##b
#define CALLP(n) PASTE(do_, n)()
#define ARGCALL(x) (x)
int do_one(void) { return 1; }
typedef int (*fn_t)(int);
static int inc(int v) { return v + 1; }
static fn_t get_fn(void) { return inc; }
int use(void) {
    unsigned short s = bswap_16(0x1234);
    int a = CALLP(one);
    int b = get_fn()(2);
    int c = ARGCALL(PASTE(do_, one)());
    return s + a + b + c;
}
