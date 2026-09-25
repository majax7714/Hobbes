# The fixture's build, for the derived artifacts only (bear records it; nothing links).
CFLAGS = -Wall -Wextra -Wno-unused-parameter -Wno-unused-function -Isrc -Ilibs -O2
OBJ = build/distance-cpu.o build/distance-sse2.o build/distance-avx2.o build/distance-avx512.o build/distance-neon.o build/distance-rvv.o
all: $(OBJ)
build/distance-avx2.o: ISA := -mavx2 -mfma
build/distance-avx512.o: ISA := -mavx512f -mavx512bw -mavx512vl -mavx512dq
build/%.o: src/%.c
	mkdir -p build && $(CC) $(CFLAGS) $(ISA) -c $< -o $@
