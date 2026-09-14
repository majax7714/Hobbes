#include "shapes.h"

namespace {

int hidden(int v) { return v + 1; }

}  // namespace

static int local(int v) { return v + 2; }

namespace shapes {

int Shape::area() const {
    return hidden(1);
}

int Shape::units() {
    return local(3);
}

Circle::Circle(int r) : radius_(r) {}

int Circle::area() const {
    return radius_ * radius_;
}

Point operator+(const Point &a, const Point &b) {
    Point out;
    out.x = a.x + b.x;
    return out;
}

int overloaded(int v) { return v; }

int overloaded(double v) { return (int)v; }

int plain(int v) { return v; }

}  // namespace shapes
