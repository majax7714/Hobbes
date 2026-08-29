package com.example.app;

/** Inheritance shapes the fallback must respect (ADR-096). */
public class Shapes {

    /** A base with an overload the subclass's call reaches. */
    public static class Base {
        protected void log(String s, int n) {
        }

        protected String label() {
            return "base";
        }
    }

    /** Declares one `log` locally; calls the inherited two-argument one. */
    public static class Derived extends Base {
        protected void log(String s) {
            log(s, 1);
        }

        /** An inner class with a superclass: its `label()` is inherited,
         *  not the outer `Shapes.label()`. */
        class Inner extends Base {
            String describe() {
                return label();
            }
        }
    }

    static String label() {
        return "outer";
    }

    static Shape unit() {
        return new Shape() {
            @Override
            public double area() {
                return 1.0;
            }
        };
    }
}
