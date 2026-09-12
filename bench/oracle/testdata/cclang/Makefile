CC = cc
CFLAGS = -Wall

all: app tool

app: main.c lib.c
	$(CC) $(CFLAGS) -o app main.c lib.c

tool: tool.c lib.c
	$(CC) $(CFLAGS) -o tool tool.c lib.c
