#include "minicpp/shapes.h"
#include "util.h"

#include <cstdio>

int main() {
    shapes::Circle c(3);
    int measured = shapes::area(1);
    int scaled = scale(3);
    int biggest = shapes::largest<int>(measured, scaled);
    std::printf("%d %d %d\n", c.area(), biggest, scaled);
    return 0;
}
