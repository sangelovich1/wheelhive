async function j(path: string, opts: RequestInit = {}) {
  const r = await fetch(path, { credentials: "include", headers: { "content-type": "application/json" }, ...opts });
  if (r.status === 401) throw new Error("unauthorized");
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}
export const api = {
  session: () => j("/api/session"),
  login: (password: string) => j("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => j("/api/logout", { method: "POST" }),
  accounts: () => j("/api/accounts"),
  positions: (account?: string) => j(`/api/positions${account ? `?account=${encodeURIComponent(account)}` : ""}`),
  summary: (account?: string) => j(`/api/portfolio/summary${account ? `?account=${encodeURIComponent(account)}` : ""}`),
};
