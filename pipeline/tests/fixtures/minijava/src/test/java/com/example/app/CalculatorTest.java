package com.example.app;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class CalculatorTest {

    @Test
    void addsInts() {
        assertEquals(4, new Calculator().twice(2));
    }

    @Test
    void rendersACircle() {
        assertEquals("area=3.141592653589793", Report.render(new Circle(1.0)));
    }

    @Test
    void padsThroughTheNestedClass() {
        assertEquals("line ", new Report.Line().text());
    }
}
