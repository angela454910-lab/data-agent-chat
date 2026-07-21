import { useMemo, useState } from 'react';
import { Table, Download, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { exportToExcel } from '../lib/export';

function tryParseJson(s: string): unknown | null {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

type SortDir = 'asc' | 'desc' | null;

function formatNumber(val: unknown): string {
  if (typeof val === 'number') {
    return val.toLocaleString();
  }
  return String(val ?? '');
}

function isNumeric(val: unknown): boolean {
  return typeof val === 'number' && !isNaN(val);
}

function JsonTable({ data, compact }: { data: Record<string, unknown>[]; compact?: boolean }) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  if (data.length === 0) return <span className="text-slate-400 italic">空结果</span>;

  const columns = Object.keys(data[0]);
  const maxRows = compact ? 10 : 20;

  // Sort data
  const sortedData = useMemo(() => {
    if (!sortCol || !sortDir) return data;
    return [...data].sort((a, b) => {
      const aVal = a[sortCol];
      const bVal = b[sortCol];

      if (isNumeric(aVal) && isNumeric(bVal)) {
        return sortDir === 'asc'
          ? (aVal as number) - (bVal as number)
          : (bVal as number) - (aVal as number);
      }

      const aStr = String(aVal ?? '');
      const bStr = String(bVal ?? '');
      return sortDir === 'asc'
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr);
    });
  }, [data, sortCol, sortDir]);

  const displayRows = sortedData.slice(0, maxRows);
  const hasMore = data.length > maxRows;

  // Determine per-column text alignment: numeric columns get text-right
  const columnAlign = (col: string): 'left' | 'right' => {
    const sample = data.slice(0, 5);
    const allNumeric = sample.every(row => isNumeric(row[col]));
    return allNumeric ? 'right' : 'left';
  };

  const handleSort = (col: string) => {
    if (sortCol === col) {
      // Cycle: asc → desc → null
      if (sortDir === 'asc') {
        setSortDir('desc');
      } else if (sortDir === 'desc') {
        setSortDir(null);
        setSortCol(null);
      }
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  const handleExport = () => {
    exportToExcel(data);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortCol !== col) return <ArrowUpDown size={10} className="text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />;
    if (sortDir === 'asc') return <ArrowUp size={10} className="text-blue-500" />;
    if (sortDir === 'desc') return <ArrowDown size={10} className="text-blue-500" />;
    return <ArrowUpDown size={10} className="text-slate-300" />;
  };

  return (
    <div>
      {/* Export button */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] text-slate-400">{data.length} 条记录</span>
        <button
          onClick={handleExport}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          title="下载 Excel"
        >
          <Download size={10} />
          <span>导出 Excel</span>
        </button>
      </div>

      {/* Table with sticky header */}
      <div className="overflow-x-auto max-h-80 overflow-y-auto rounded-lg border border-slate-200 table-sticky">
        <table className="text-xs border-collapse min-w-full">
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className={[
                    'group cursor-pointer select-none px-2 py-1.5 bg-slate-50 text-slate-600 font-medium border-b border-slate-200 whitespace-nowrap',
                    columnAlign(col) === 'right' ? 'text-right' : 'text-left',
                  ].join(' ')}
                >
                  <div className={['flex items-center gap-1', columnAlign(col) === 'right' ? 'justify-end' : 'justify-start'].join(' ')}>
                    <span>{col}</span>
                    <SortIcon col={col} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                {columns.map(col => (
                  <td
                    key={col}
                    className={[
                      'px-2 py-1 text-slate-600 border-b border-slate-100 whitespace-nowrap max-w-[200px] truncate',
                      columnAlign(col) === 'right' ? 'text-right tabular-nums' : 'text-left',
                    ].join(' ')}
                    title={String(row[col] ?? '')}
                  >
                    {row[col] === null || row[col] === undefined
                      ? <span className="text-slate-300">—</span>
                      : formatNumber(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <div className="text-[10px] text-slate-400 mt-1 px-1">
          显示 {displayRows.length} / {data.length} 行
          <span className="ml-1 text-slate-300">(导出可获取全部数据)</span>
        </div>
      )}
    </div>
  );
}

export function StepDetail({ detail, compact }: { detail: string; compact?: boolean }) {
  const rendered = useMemo(() => {
    const trimmed = detail.trim();
    const parsed = tryParseJson(trimmed);

    if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'object' && parsed[0] !== null) {
      return (
        <div className="flex items-start gap-1.5">
          <Table size={10} className="text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <JsonTable data={parsed as Record<string, unknown>[]} compact={compact} />
          </div>
        </div>
      );
    }

    if (parsed !== null && typeof parsed === 'object') {
      return (
        <pre className="text-[11px] text-slate-500 whitespace-pre-wrap break-all">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      );
    }

    return (
      <pre className="text-[11px] text-slate-500 whitespace-pre-wrap break-words">
        {detail}
      </pre>
    );
  }, [detail, compact]);

  return rendered;
}