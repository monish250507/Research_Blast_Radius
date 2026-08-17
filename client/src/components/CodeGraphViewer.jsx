import React from 'react';

export default function CodeGraphViewer({ symbols }) {
  if (!symbols || symbols.length === 0) {
    return (
      <div className="p-4 text-center text-slate-700 font-mono text-xs font-bold">
        No code AST symbols indexed. Input a GitHub URL or code files.
      </div>
    );
  }

  return (
    <div className="space-y-4 w-full overflow-hidden">
      <div className="flex flex-col items-start border-b-2 border-black pb-2 gap-0.5">
        <div className="flex items-center justify-between w-full">
          <h3 className="text-xs font-extrabold text-black uppercase tracking-wider font-mono">
            Indexed Code AST Symbols ({symbols.length})
          </h3>
          <span className="text-[11px] font-mono font-bold text-slate-700">AST Index</span>
        </div>
        <p className="text-[11px] font-mono font-semibold text-slate-600">
          Variables, hyperparameters, and AST symbols indexed by source file line.
        </p>
      </div>

      <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1 w-full">
        {symbols.map((sym, idx) => (
          <div
            key={idx}
            className="bg-white border-2 border-black p-3 rounded-md font-mono text-xs shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] w-full flex flex-col space-y-1.5 overflow-hidden"
          >
            {/* Row 1: Symbol Name & Type Badge */}
            <div className="flex items-center justify-between gap-2 w-full">
              <span className="text-black font-extrabold text-xs truncate break-all" title={sym.symbol}>
                {sym.symbol}
              </span>
              <span className="text-[10px] uppercase bg-sky-200 border border-black text-black font-bold px-1.5 py-0.5 rounded whitespace-nowrap">
                {sym.type}
              </span>
            </div>

            {/* Row 2: File Anchor & Line Number */}
            <div className="flex items-center justify-between text-slate-700 font-bold text-[11px] w-full pt-0.5 border-t border-slate-200">
              <span className="truncate max-w-[180px]" title={sym.file}>
                {sym.file}
              </span>
              <span className="text-black font-extrabold whitespace-nowrap">Line {sym.line}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
