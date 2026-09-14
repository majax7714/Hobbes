CXX = g++
CXXFLAGS = -Wall -I.

all: app tool

app: main.cpp shapes.cpp
	$(CXX) $(CXXFLAGS) -o app main.cpp shapes.cpp

tool: tool.cpp shapes.cpp
	$(CXX) $(CXXFLAGS) -o tool tool.cpp shapes.cpp
