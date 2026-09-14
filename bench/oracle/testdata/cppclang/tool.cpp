#include "shapes.h"

int main() {
    shapes::Circle c(4);
    return c.twice() + shapes::plain(5);
}
