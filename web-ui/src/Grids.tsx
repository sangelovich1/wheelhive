import { AgGridReact } from "ag-grid-react";
import {
  ModuleRegistry,
  AllCommunityModule,
  themeQuartz,
  colorSchemeDark,
} from "ag-grid-community";

ModuleRegistry.registerModules([AllCommunityModule]);
const darkTheme = themeQuartz.withPart(colorSchemeDark);

export function Grid({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = rows.length
    ? Object.keys(rows[0]).map((f) => ({ field: f, sortable: true, filter: true, resizable: true }))
    : [];
  return (
    <div style={{ height: 340, width: "100%" }}>
      <AgGridReact rowData={rows} columnDefs={cols} theme={darkTheme} />
    </div>
  );
}
