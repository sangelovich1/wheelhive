import { useEffect, useState } from "react";
import { api } from "./api";
import { Login } from "./Login";
import { Dashboard } from "./Dashboard";

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    api.session().then((s) => setAuthed(s.authenticated)).catch(() => setAuthed(false));
  }, []);

  if (authed === null) return <div style={{ padding: 16 }}>Loading…</div>;
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  return <Dashboard />;
}
