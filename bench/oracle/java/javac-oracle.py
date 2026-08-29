#!/usr/bin/env python3
"""The wrapping javac (the scip-java trick): forwards to the real javac
with the HobbesOracle plugin attached. Maven runs it through
`-Dmaven.compiler.executable=<this> -Dmaven.compiler.fork=true`; the
Gradle path uses `hobbes-oracle.gradle` instead (a toolchain forbids
`forkOptions.executable`).

Argument files (`@path`) are expanded — Maven writes one when the
command is long — the plugin jar joins the processor path when the build
sets one (annotation processors then still discover), else the class
path, and the JVM exports the one javac internal the plugin reads.
"""
import os
import shlex
import subprocess
import sys

JAR = os.environ["HOBBES_ORACLE_JAR"]
JAVAC = os.path.join(os.environ.get("JAVA_HOME", "/usr/local/java"), "bin", "javac")
EXPORTS = [
    "-J--add-exports=jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED",
    "-J--add-exports=jdk.compiler/com.sun.tools.javac.code=ALL-UNNAMED",
]


def expand(args):
    out = []
    for a in args:
        if a.startswith("@") and os.path.isfile(a[1:]):
            with open(a[1:], encoding="utf-8") as f:
                out.extend(shlex.split(f.read()))
        else:
            out.append(a)
    return out


def main():
    args = expand(sys.argv[1:])
    sep = os.pathsep
    placed = False
    for i, a in enumerate(args):
        if a in ("-processorpath", "--processor-path") and i + 1 < len(args):
            args[i + 1] = args[i + 1] + sep + JAR
            placed = True
            break
    if not placed:
        for i, a in enumerate(args):
            if a in ("-classpath", "-cp", "--class-path") and i + 1 < len(args):
                args[i + 1] = args[i + 1] + sep + JAR
                placed = True
                break
    if not placed:
        args = ["-classpath", JAR] + args
    cmd = [JAVAC, *EXPORTS, *args, "-Xplugin:HobbesOracle"]
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
