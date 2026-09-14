#include "minicpp/shapes.h"

#include <utility>

namespace shapes {

static int bump(int a) {
    return a + 1;
}

int Shape::area() const {
    return 0;
}

int Circle::area() const {
    return bump(r_) * this->radius();
}

int Circle::unit() {
    return 1;
}

int area(int n) {
    return n;
}

int area(double n) {
    return (int)(n);
}

int measure(const Circle &c, const Circle *p, int (*fp)(int)) {
    int here = c.radius();
    int there = p->area();
    int piped = (*fp)(here);
    int twice = TWICE(there);
    auto scaled = [](int n) { return bump(n); };
    int lambda = scaled(piped);
    Circle made(2);
    Circle *fresh = new Circle(1);
    int biggest = largest<int>(here, there);
    int one = Circle::unit();
    int moved = std::move(one);
    delete fresh;
    return here + there + piped + twice + lambda + biggest + moved + made.radius();
}

}  // namespace shapes
