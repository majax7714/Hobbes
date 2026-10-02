import os.path

import minireexport as mr


def build():
    first = mr.Beta()
    second = mr.Gamma()
    return first, second, mr.two(1), mr.CONST


def where(path):
    return os.path.dirname(path)
