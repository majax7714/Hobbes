#!/bin/sh
# Build the HobbesOracle javac plugin jar with the JDK alone (no Maven,
# no network): javac + jar, inside the sandbox image where the JDK
# lives. Output: <out>/hobbes-oracle.jar.
#   build.sh <out-dir>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
out=$1
mkdir -p "$out/classes"
javac -source 17 -target 17 -Xlint:-options \
  --add-exports jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED \
  --add-exports jdk.compiler/com.sun.tools.javac.code=ALL-UNNAMED \
  -d "$out/classes" "$here/src/hobbes/oracle/HobbesOracle.java"
mkdir -p "$out/classes/META-INF/services"
cp "$here/src/META-INF/services/com.sun.source.util.Plugin" "$out/classes/META-INF/services/"
jar --create --file "$out/hobbes-oracle.jar" -C "$out/classes" .
echo "$out/hobbes-oracle.jar"
