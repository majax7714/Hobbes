// member.cpp — a member call whose object expression spans two lines
// (H-28). The MemberExpr of `.str()` and of `.get()` begins at the
// object's first token, on line 25, and ends at the member's own token,
// on line 26: the site is the member's, which is where Hobbes and
// scip-clang both hold it.

namespace chain {

struct Wrapped {
    int v;
    int get() const { return v; }
};

struct Builder {
    int total;
    Builder &operator<<(int n) {
        total += n;
        return *this;
    }
    Wrapped str() const { return Wrapped{total}; }
};

int build() {
    Builder m{0};
    return (m << 1
              << 2).str().get();
}

}  // namespace chain
