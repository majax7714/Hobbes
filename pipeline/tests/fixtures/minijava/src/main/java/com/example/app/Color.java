package com.example.app;

/** Enum constants with arguments invoke the enum's constructor. */
public enum Color {
    RED(1),
    GREEN(2);

    private final int code;

    Color(int code) {
        this.code = code;
    }

    public int code() {
        return code;
    }
}
