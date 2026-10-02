export function html(strings: TemplateStringsArray, ...values: unknown[]): string {
  return strings.join(String(values.length));
}
export function count(n: number): number {
  return n + 1;
}
export const ns = { html };
export function page(n: number): string {
  return html`<p>${count(n)}</p>`;
}
export function viaMember(): string {
  return ns.html`<b></b>`;
}
