#ifdef _WIN32
static int sep(void) {
    return '\\';
}
#else
static int sep(void) {
    return '/';
}
#endif

int path_separator(void) {
    return sep();
}
