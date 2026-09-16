// macroqual.cpp — a call whose qualifier comes from a macro body and
// whose name comes from the macro argument (H-31). fmt's os.h:57 is
// `#define FMT_SYSTEM(call) ::call`, read at src/os.cc:176 through
// FMT_RETRY_VAL: clang spells the callee's range begin at the macro
// body's `::` and its range end at the author's own name token, so the
// site keyed on the `#define`'s line — in fmt, another file — until the
// reader took the end (ADR-113 §3).

struct Str {
    const char *p;
    const char *c_str() const { return p; }
};

int g(const char *s) { return s ? 0 : -1; }

namespace ns {

int h(int n) { return n + 1; }

template <typename T>
T t(T v) { return v; }

}  // namespace ns

// SYS is FMT_SYSTEM's shape — the body supplies the qualifier and the
// argument supplies the name — and RETRY wraps it as FMT_RETRY_VAL
// wraps it, so the call reaches the front end through two expansions.
#define SYS(call) ::call
#define RETRY(expr) ((expr) < 0 ? -1 : 0)

int run(const Str &s) {
    return RETRY(SYS(g(s.c_str())));
}

// The same call unwrapped, H-31's other half: with no outer macro the
// begin is no argument's expansion, so the site was the expansion's own
// — the `SYS` token's column here, in fmt a line inside FMT_RETRY_VAL's
// body (os.h:62), which is how six calls collapsed onto two lines.
int once(const Str &s) {
    return SYS(g(s.c_str()));
}

// The control: qualified calls with neither end in a macro.
int plain() {
    return ns::h(1) + ns::t<int>(2);
}

// And the same qualified call inside a macro's argument, where clang
// flags both of its ends an argument expansion exactly as it flags the
// macro body's `::` above: both ends are the author's own tokens, on
// the line of the use, so this keys at its qualifier as `plain`'s do.
int wrapped() {
    return RETRY(ns::h(2));
}
