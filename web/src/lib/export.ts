import * as XLSX from 'xlsx';

export function exportToExcel(data: Record<string, unknown>[], filename?: string): void {
  const ws = XLSX.utils.json_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Data');

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const name = filename || `data-export-${timestamp}`;

  XLSX.writeFile(wb, `${name}.xlsx`);
}