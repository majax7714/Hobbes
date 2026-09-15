// converter@4's fixture (ADR-101's 2026-09-15 amendment): a #define
// spelled with spaces after the #, and a declaration head split over lines.
#ifndef GRAIN_H
#  define TWICE(x) ((x) * 2)
#endif

template <typename T>
typename T::value_type
pick(const T &c) { return c.front(); }

inline int plain(int v) { return TWICE(v); }

inline int use(int v) {
  return plain(v) + TWICE(v);
}
struct box { using value_type = int; int front() const { return 1; } };
inline int first() { return pick(box{}); }
