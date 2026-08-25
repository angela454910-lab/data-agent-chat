import { useRef, useState } from 'react';
import { Upload, FileSpreadsheet, X, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import type { Dataset } from '../types';

interface Props {
  dataset: Dataset | null;
  onUpload: (file: File) => Promise<void>;
  onDelete: () => void;
  uploading: boolean;
}

export function DatasetUploader({ dataset, onUpload, onDelete, uploading }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = (file: File | undefined) => {
    if (!file) return;
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['xlsx', 'xls', 'json', 'csv'].includes(ext || '')) {
      alert('Please upload an Excel (.xlsx), JSON (.json), or CSV (.csv) file');
      return;
    }
    onUpload(file);
  };

  if (dataset) {
    return (
      <div className="mb-2 rounded-xl border border-slate-200 bg-slate-50/80 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2">
          <FileSpreadsheet size={14} className="text-emerald-600 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-slate-700 truncate block">
              {dataset.name}
            </span>
            <span className="text-[10px] text-slate-400">
              {dataset.row_count} rows | {dataset.columns.length} cols
            </span>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 rounded hover:bg-slate-200 text-slate-400 transition-colors"
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          <button
            onClick={onDelete}
            className="p-1 rounded hover:bg-red-100 text-slate-400 hover:text-red-500 transition-colors"
            title="Remove dataset"
          >
            <X size={12} />
          </button>
        </div>
        {expanded && (
          <div className="border-t border-slate-200 px-3 py-2 max-h-40 overflow-y-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="text-slate-400 border-b border-slate-200">
                  <th className="text-left py-1 pr-2 font-normal">Column</th>
                  <th className="text-left py-1 pr-2 font-normal">Type</th>
                  <th className="text-left py-1 font-normal">Samples</th>
                </tr>
              </thead>
              <tbody>
                {dataset.columns.map((col) => (
                  <tr key={col.name} className="border-b border-slate-100 last:border-0">
                    <td className="py-1 pr-2 font-medium text-slate-600">{col.name}</td>
                    <td className="py-1 pr-2 text-slate-400">{col.type}</td>
                    <td className="py-1 text-slate-400 truncate max-w-32" title={col.sample_values}>
                      {col.sample_values}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={`mb-2 rounded-xl border-2 border-dashed transition-colors ${
        dragOver ? 'border-blue-400 bg-blue-50' : 'border-slate-200 hover:border-slate-300'
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFileSelect(e.dataTransfer.files[0]);
      }}
    >
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 text-xs text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50"
      >
        {uploading ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload size={14} />
            Upload Excel or JSON
          </>
        )}
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls,.json,.csv"
        className="hidden"
        onChange={(e) => {
          handleFileSelect(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}
