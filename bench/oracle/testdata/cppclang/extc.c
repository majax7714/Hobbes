/* extc.c — the bare-name fallback's own case, in the two languages it
   arises in: a C unit, where nothing is mangled at all, and an
   `extern "C"` declaration in a C++ one. This unit calls what extc2.c
   defines, and defines the `main` extc2.c calls. */

#ifdef __cplusplus
extern "C" {
#endif

int shared_entry(int v);

#ifdef __cplusplus
}
#endif

int main(void) {
    return shared_entry(1);
}
