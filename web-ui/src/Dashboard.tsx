import { useEffect, useState } from "react";
import { api } from "./api";
import { Grid } from "./Grids";
export function Dashboard() {
  const [accounts, setAccounts] = useState<string[]>([]);
  const [acct, setAcct] = useState<string | undefined>();
  const [pos, setPos] = useState<{ stocks: any[]; options: any[] }>({ stocks: [], options: [] });
  const [sum, setSum] = useState<any>(null);
  const load = async () => { setPos(await api.positions(acct)); setSum(await api.summary(acct)); };
  useEffect(() => { api.accounts().then(a => setAccounts(a.accounts)); }, []);
  useEffect(() => { load(); }, [acct]);
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h2>Positions</h2>
        <select value={acct ?? ""} onChange={e => setAcct(e.target.value || undefined)}>
          <option value="">All accounts</option>
          {accounts.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <button onClick={load}>Refresh</button>
        <button onClick={() => api.logout().then(() => location.reload())} style={{ marginLeft: "auto" }}>Sign out</button>
      </div>
      {sum && <div style={{ display: "flex", gap: 16, margin: "12px 0" }}>
        <Tile label={`YTD unrealized P/L`} value={sum.stocks_unrealized} />
        <Tile label={`Year`} value={sum.year} />
      </div>}
      <h3>Stock Holdings</h3><Grid rows={pos.stocks} />
      <h3>Open Options</h3><Grid rows={pos.options} />
    </div>
  );
}
function Tile({ label, value }: { label: string; value: unknown }) {
  return <div style={{ border: "1px solid #333", borderRadius: 8, padding: "8px 16px" }}>
    <div style={{ opacity: .7, fontSize: 12 }}>{label}</div>
    <div style={{ fontSize: 22 }}>{String(value)}</div>
  </div>;
}
