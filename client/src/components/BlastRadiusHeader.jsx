import React from 'react';

export default function BlastRadiusHeader({ analysis, hasCode, hasPaper, isIngesting, isAnalyzing, onExportReport }) {
  const score = analysis?.overall_impact_score ?? 0;
  const risk = analysis?.risk_level || 'NONE';
  const confidence = analysis?.confidence_score ?? 0;
  const summary = analysis?.impact_summary || { sections_affected: 0, equations_affected: 0, tables_affected: 0 };
  const executionTimeMs = analysis?.execution_time_ms || 0;
  const costEst = analysis?.cost_efficiency?.estimated_cost_usd ?? 0.00;

  const getRiskClass = (r) => {
    switch ((r || '').toUpperCase()) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MAJOR': return 'badge-major';
      case 'MINOR': return 'badge-minor';
      default: return 'badge-none';
    }
  };

  return (
    <header className="border-b-2 border-black bg-white px-6 py-5 shadow-[0_4px_0_0_rgba(0,0,0,1)] text-center w-full">
      <div className="max-w-4xl mx-auto space-y-3 flex flex-col items-center justify-center">
        
        {/* Title & Multi-Agent Subtitle */}
        <div className="flex flex-col items-center justify-center gap-1">
          <div className="flex items-center justify-center gap-2.5">
            <h1 className="text-xl font-extrabold tracking-tight text-black uppercase font-mono text-center">
              Research Code & Paper Impact Analyzer
            </h1>
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 border border-black"></span>
          </div>
          <p className="text-xs font-mono font-bold text-slate-700 text-center max-w-xl">
            Multi-Agent AI Architecture: Code AST Traversal Agent + Manuscript Impact Analyst + Skeptic Verification Arbiter.
          </p>
        </div>

        {/* Stepped Progress & Multi-Agent Tracker */}
        <div className="flex flex-col items-center gap-1.5 pt-1">
          <div className="flex flex-wrap items-center justify-center gap-3 font-mono text-[11px] font-bold">
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasCode ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>1. Code AST Agent</span>
            </div>
            <span className="text-black font-extrabold">→</span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasPaper ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>2. Manuscript Analyst Agent</span>
            </div>
            <span className="text-black font-extrabold">→</span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${analysis ? 'bg-sky-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>3. Skeptic Verification Arbiter</span>
            </div>
          </div>
          <span className="text-[10px] font-mono font-semibold text-slate-500">
            Workflow: Extract AST Symbols → Cross-Reference Paper Structure → Audit & Synthesize Revisions
          </span>
        </div>

        {/* Metrics & Cost Audit Badges */}
        {analysis ? (
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <div className="flex items-center justify-center gap-5 bg-white border-2 border-black px-6 py-2.5 rounded-md font-mono text-xs shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              {/* Score */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Blast Radius Score</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xl font-extrabold text-black">{score}%</span>
                  <span className={`badge ${getRiskClass(risk)}`}>{risk}</span>
                </div>
              </div>

              {/* Confidence & Cost Audit */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Confidence Rating</span>
                <span className="text-black font-extrabold text-sm mt-0.5">{confidence}%</span>
              </div>

              {/* Cost Efficiency */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Cost Audit</span>
                <span className="text-emerald-700 font-extrabold text-xs mt-0.5">${costEst.toFixed(2)} (Groq LPU)</span>
              </div>

              {/* Counts */}
              <div className="flex items-center justify-center gap-4 text-black font-bold">
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Sections</span>
                  <span className="font-extrabold text-black mt-0.5 block">{summary.sections_affected}</span>
                </div>
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Equations</span>
                  <span className="font-extrabold text-black mt-0.5 block">{summary.equations_affected}</span>
                </div>
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Time</span>
                  <span className="font-extrabold text-black mt-0.5 block">{(executionTimeMs / 1000).toFixed(2)}s</span>
                </div>
              </div>
            </div>

            {/* Export Audit Report Button */}
            {onExportReport && (
              <button
                className="neo-btn text-xs"
                onClick={onExportReport}
              >
                Export Audit Report (.json)
              </button>
            )}
          </div>
        ) : (
          <div className="text-xs font-mono font-bold text-black bg-white border-2 border-black px-4 py-1.5 rounded-md shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] text-center">
            {isIngesting ? 'Ingesting Code & Document...' : isAnalyzing ? 'Calculating Blast Radius Across 3 Agents...' : 'Awaiting Data Input to Begin Multi-Agent Analysis'}
          </div>
        )}
      </div>
    </header>
  );
}
