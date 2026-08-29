package com.example.app;

/** The overload pair, constructor chaining, and a generic method. */
public class Calculator {
    private final int seed;

    public Calculator() {
        this(0);
    }

    public Calculator(int seed) {
        this.seed = seed;
    }

    public int add(int a, int b) {
        return a + b + seed;
    }

    public double add(double a, double b) {
        return a + b;
    }

    public int twice(int x) {
        return add(x, x);
    }

    public <T> T pick(T first, T second) {
        return first;
    }

    public static Calculator of() {
        return new Calculator();
    }
}
