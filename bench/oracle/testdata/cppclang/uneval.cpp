// uneval.cpp — a call written inside an unevaluated operand (H-32,
// ADR-121 §3). clang keeps the `CallExpr` under a
// `UnaryExprOrTypeTraitExpr` (`sizeof`, `alignof`), a `CXXNoexceptExpr`
// and a `RequiresExpr`, and O10's reader recorded every call kind it met
// on the way down, so the key held a site for a call no instruction
// follows. Lane A stopped drawing these at 0.2.33-beta (ADR-121 §1) on
// the same list, `typeid` excepted on both sides: `typeid`'s operand is
// evaluated when it is a glvalue of polymorphic class type
// ([expr.typeid]/3), which neither side can type, so its sites stay.

#include <typeinfo>

int f(int n) { return n + 1; }

constexpr bool g() { return true; }

struct P {
    virtual ~P() {}
};

P &p() {
    static P only;
    return only;
}

// Dropped: the operand of a `sizeof`, written both ways.
unsigned long s1 = sizeof(f(1));
unsigned long s2 = sizeof f(1);

// No site either way: an `alignof` over a `decltype` names a type, and a
// `decltype`'s operand never reaches the reader — clang prints it as
// part of a type string and never walks it (ADR-121 §3).
unsigned long s3 = alignof(decltype(f(1)));

// Dropped: a `noexcept` expression's operand, as an initialiser. The
// same expression as a `noexcept` specifier's own condition, below, is
// `decltype`'s case over again — clang prints it as part of the
// declaration's type and dumps no node for it — so that line has never
// keyed a site and does not count as one dropped.
bool n1 = noexcept(f(1));
void h() noexcept(noexcept(f(1)));

// Dropped: a requirement inside a requires-expression.
template <typename T>
requires requires { f(1); }
void k(T) {}

// Kept, both of them: `typeid`'s operand, on a non-polymorphic result
// (unevaluated in truth) and on a polymorphic glvalue (evaluated in
// truth). The syntax cannot tell them apart and the conservative side is
// to keep the site, which is the rule lane A also keeps.
const std::type_info &t1 = typeid(f(1));
const std::type_info &t2 = typeid(p());

// Kept: a constant expression is not an unevaluated operand — the
// compiler evaluates `static_assert`'s condition and the dump holds it.
static_assert(g(), "");

// Kept: the evaluated call on a line that also carries an unevaluated
// one — H-30's shape, so a line holding both still keys the real call.
int both() { return (int)sizeof(f(1)) + f(3); }
