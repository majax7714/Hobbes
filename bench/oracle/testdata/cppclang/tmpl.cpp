// tmpl.cpp — two class templates with a same-named static member
// (H-29). A pattern member carries no mangled name, so its class is the
// only thing that tells `A::format_as` from `B::format_as`; each
// template's own member function calls its own.

template <typename T>
struct A {
    static int format_as(int v) { return v + 1; }
    int use() const { return format_as(1); }
};

template <typename T>
struct B {
    static int format_as(int v) { return v + 2; }
    int use() const { return format_as(2); }
};

int run() {
    A<int> a;
    B<int> b;
    return a.use() + b.use();
}
