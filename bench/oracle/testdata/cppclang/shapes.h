#ifndef CPPCLANG_SHAPES_H
#define CPPCLANG_SHAPES_H

namespace shapes {

class Shape {
public:
    virtual int area() const;
    int twice() const { return area() + 1; }
    static int units();
};

class Circle : public Shape {
public:
    explicit Circle(int r);
    int area() const;
    int radius_;
};

struct Point {
    int x;
};

Point operator+(const Point &a, const Point &b);

template <typename T>
T twice_t(T v) {
    return v + v;
}

int overloaded(int v);
int overloaded(double v);

int plain(int v);

}  // namespace shapes

#define CALL_PLAIN(x) shapes::plain((x))

#endif
