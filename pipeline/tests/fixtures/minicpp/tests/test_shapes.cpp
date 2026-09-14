#include "minicpp/shapes.h"
#include "util.h"

// gtest is not vendored here, and the walk never needs it: a stub with
// the same shape gives the parse exactly what a gtest file's gives it —
// a function definition whose declarator names the macro.
#define TEST(suite, name) void suite##_##name()

TEST(Shapes, Area) {
    shapes::Circle c(2);
    int measured = c.area();
    (void)measured;
}

TEST(Shapes, Scale) {
    int scaled = scale(4);
    (void)scaled;
}
