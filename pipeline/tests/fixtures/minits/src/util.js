// Shared helpers for the minits fixture app.
export function normalize(name) {
  return name.trim().toLowerCase();
}

export function apiBase() {
  return process.env.MINITS_API_URL || "http://localhost";
}
