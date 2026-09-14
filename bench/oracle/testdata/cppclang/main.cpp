#include "shapes.h"

namespace {

struct Runner {
    int run() { return this->step() + 1; }
    int step() { return 2; }
};

}  // namespace

int apply(int (*fp)(int), int v) {
    return fp(v);
}

int main() {
    int r = shapes::plain(1);
    r += shapes::Shape::units();
    r += CALL_PLAIN(2);
    r += shapes::twice_t<int>(3);
    r += shapes::overloaded(4);
    r += shapes::overloaded(5.0);
    shapes::Circle c(1);
    shapes::Shape *p = &c;
    r += p->area();
    r += c.twice();
    shapes::Circle *heap = new shapes::Circle(2);
    r += heap->area();
    r += shapes::Circle(3).area();
    shapes::Point a{1};
    shapes::Point b{2};
    shapes::Point s = a + b;
    shapes::Point copy = s;
    Runner runner;
    r += runner.run();
    r += apply(shapes::plain, 6);
    return r + s.x + copy.x;
}
