import { useState } from "react";
import { api } from "./api";
export function Login({ onOk }: { onOk: () => void }) {
  const [pw, setPw] = useState(""); const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api.login(pw); onOk(); } catch { setErr("Invalid password"); }
  };
  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "20vh auto", display: "grid", gap: 8 }}>
      <h2>WheelHive</h2>
      <input type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="Password" autoFocus />
      <button type="submit">Sign in</button>
      {err && <span style={{ color: "crimson" }}>{err}</span>}
    </form>
  );
}
