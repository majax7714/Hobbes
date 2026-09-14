#ifndef MINICPP_SHAPES_H
#define MINICPP_SHAPES_H

#define MINICPP_VERSION 1
#define TWICE(x) ((x) * 2)

namespace shapes {

class Shape {
public:
    virtual ~Shape() {}
    virtual int area() const;
    int doubled() const { return TWICE(area()); }
};

class Circle : public Shape {
public:
    Circle(int r) : r_(r) {}
    int radius() const { return r_; }
    static int unit();
    virtual int area() const;

private:
    int r_;
};

template <typename T>
T largest(T a, T b) {
    return a > b ? a : b;
}

int area(int n);
int area(double n);

}  // namespace shapes

#endif
