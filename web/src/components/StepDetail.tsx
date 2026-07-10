import { useMemo } from 'react';
import { Table } from 'lucide-react';

function tryParseJson(s: string): unknown | null {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function JsonTable({ data, compact }: { data: Record<string, unknown>[]; compact?: boolean }) {
  if (data.length === 0) return <span className="text-slate-400 italic">空结果</span>;

  const columns = Object.keys(data[0]);
  const maxRows = compact ? 10 : 20;
  const displayRows = data.slice(0, maxRows);
  const hasMore = data.length > maxRows;

  return (
    <div className="overflow-x-auto">
      <table className="text-[10px] border-collapse min-w-full">
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col}
                className="text-left px-1.5 py-0.5 bg-slate-100 text-slate-500 font-medium border-b border-slate-200 whitespace-nowrap"
              >
                {col}
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
                  className="px-1.5 py-0.5 text-slate-600 border-b border-slate-100 whitespace-nowrap max-w-[160px] truncate"
                  title={String(row[col] ?? '')}
                >
                  {row[col] === null || row[col] === undefined
                    ? <span className="text-slate-300">—</span>
                    : String(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {hasMore && (
        <div className="text-[9px] text-slate-400 mt-0.5 px-1">
          显示 {displayRows.length} / {data.length} 行
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
            <div className="text-[9px] text-slate-400 mb-0.5">{parsed.length} 条记录</div>
            <JsonTable data={parsed as Record<string, unknown>[]} compact={compact} />
          </div>
        </div>
      );
    }

    if (parsed !== null && typeof parsed === 'object') {
      return (
        <pre className="text-[10px] text-slate-500 whitespace-pre-wrap break-all">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      );
    }

    return (
      <pre className="text-[10px] text-slate-500 whitespace-pre-wrap break-words">
        {detail}
      </pre>
    );
  }, [detail, compact]);

  return rendered;
}
