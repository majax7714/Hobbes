CC = cc
CFLAGS = -Iinclude -Isrc -Wall

all: minic

minic: src/main.c src/util.c src/shapes.c
	$(CC) $(CFLAGS) -o minic src/main.c src/util.c src/shapes.c

test: tests/test_util.c src/util.c
	$(CC) $(CFLAGS) -o test_util tests/test_util.c src/util.c

clean:
	rm -f minic test_util
