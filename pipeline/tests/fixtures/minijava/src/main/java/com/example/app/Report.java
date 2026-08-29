package com.example.app;

import java.util.List;

import com.example.util.Strings;

/** Nested and anonymous classes, a lambda, a method reference, an env read. */
public class Report {

    public static String render(Shape shape) {
        return "area=" + shape.area();
    }

    /** A nested class calling across packages through an import. */
    public static class Line {
        public String text() {
            return Strings.pad("line");
        }
    }

    public Runnable job() {
        return new Runnable() {
            @Override
            public void run() {
                render(new Circle(1.0));
                tick();
            }

            private void tick() {
            }
        };
    }

    public long each(List<Shape> shapes) {
        shapes.forEach(shape -> render(shape));
        return shapes.stream().map(Report::render).count();
    }

    public String home() {
        return new StringBuilder(System.getenv("MINIJAVA_HOME")).toString();
    }
}
