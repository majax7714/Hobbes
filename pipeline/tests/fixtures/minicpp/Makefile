CXX = g++
CXXFLAGS = -Iinclude -Isrc -Wall

all: minicpp

minicpp: src/main.cpp src/shapes.cpp src/util.cpp
	$(CXX) $(CXXFLAGS) -o minicpp src/main.cpp src/shapes.cpp src/util.cpp

# Compiled, not linked: the test file's gtest macro is a local stub (no
# gtest is vendored here), so there is no test runner to link against.
test: tests/test_shapes.cpp
	$(CXX) $(CXXFLAGS) -c tests/test_shapes.cpp -o test_shapes.o

clean:
	rm -f minicpp test_shapes.o
