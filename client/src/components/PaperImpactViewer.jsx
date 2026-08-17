import React, { useState } from 'react';

export default function PaperImpactViewer({ paperAST, analysis }) {
  const [activeDiffSection, setActiveDiffSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  if (!paperAST || !paperAST.sections) {
    return (
      <div className="p-6 text-center text-slate-700 font-mono text-xs font-bold">
        No paper manuscript loaded. Paste LaTeX or upload PDF/Word document to begin.
      </div>
    );
  }

  const affectedMap = new Map();
  (analysis?.affected_sections || []).forEach((sec) => {
    affectedMap.set(sec.section_id, sec);
  });

  const getRiskClass = (risk) => {
    switch ((risk || '').toUpperCase()) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MAJOR': return 'badge-major';
      case 'MINOR': return 'badge-minor';
      default: return 'badge-none';
    }
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatTitle = (titleStr) => {
    if (!titleStr) return 'Section';
    return titleStr
      .replace(/^sec-\d+-/, '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="space-y-6">
      {/* Paper Header */}
      <div className="flex flex-col items-start border-b-2 border-black pb-3 gap-0.5">
        <div className="flex items-center justify-between w-full">
          <h2 className="text-xs font-extrabold text-black uppercase tracking-wider font-mono">
            Manuscript Section Impact Matrix ({paperAST.sections.length} Sections)
          </h2>
          <span className="text-[11px] font-mono font-bold text-slate-700">
            LaTeX / Structural AST View
          </span>
        </div>
        <p className="text-[11px] font-mono font-semibold text-slate-600">
          Flags affected paper sections, assigns risk ratings, and generates proposed side-by-side LaTeX text diffs.
        </p>
      </div>

      {/* Sections List */}
      <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
        {paperAST.sections.map((section) => {
          const impact = affectedMap.get(section.id);
          const isAffected = !!impact;
          const isDiffOpen = activeDiffSection === section.id;

          return (
            <div
              key={section.id}
              className={`border-2 border-black rounded-lg p-4 transition-all ${
                isAffected
                  ? 'bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]'
                  : 'bg-slate-50 opacity-90 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-extrabold text-black font-mono">
                      {formatTitle(section.title)}
                    </h3>
                    {isAffected ? (
                      <span className={`badge ${getRiskClass(impact.risk)}`}>
                        {impact.risk} RISK
                      </span>
                    ) : (
                      <span className="badge badge-none">UNAFFECTED</span>
                    )}
                    {isAffected && impact.confidence && (
                      <span className="text-[11px] font-mono font-bold text-slate-700">
                        {impact.confidence}% CONFIDENCE
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-mono font-bold text-slate-600 mt-1">
                    Lines {section.startLine} – {section.endLine}
                  </p>
                </div>

                {isAffected && (
                  <button
                    className="neo-btn-white text-xs py-1 px-3"
                    onClick={() => setActiveDiffSection(isDiffOpen ? null : section.id)}
                  >
                    {isDiffOpen ? 'Close Diff' : 'View Proposed Revision'}
                  </button>
                )}
              </div>

              {/* Impact Reason */}
              {isAffected && impact.reason && (
                <div className="mt-3 bg-amber-50 border-2 border-black p-3 rounded-md text-xs font-mono shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                  <span className="text-black font-extrabold block text-[11px] uppercase tracking-wider mb-1">
                    Impact Analysis
                  </span>
                  <p className="text-black font-semibold leading-relaxed font-sans text-xs">
                    {impact.reason}
                  </p>
                </div>
              )}

              {/* Side-by-Side Paper Text Diff View */}
              {isDiffOpen && impact && (
                <div className="mt-4 border-t-2 border-black pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold text-black uppercase font-mono">
                      Manuscript Text Difference (Current vs Proposed)
                    </span>
                    <button
                      className="neo-btn text-xs py-1 px-3"
                      onClick={() => handleCopy(impact.suggested_text || '', section.id)}
                    >
                      {copiedId === section.id ? 'Copied to Clipboard' : 'Copy Revised LaTeX'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                    {/* Current Text */}
                    <div className="bg-rose-100 border-2 border-black p-3.5 rounded-md shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                      <span className="text-[10px] font-extrabold text-rose-900 uppercase tracking-wider block mb-2">
                        Current Paper Text
                      </span>
                      <pre className="whitespace-pre-wrap text-black font-bold text-[11px] leading-relaxed">
                        {impact.current_text || section.text}
                      </pre>
                    </div>

                    {/* Proposed Revised Text */}
                    <div className="bg-emerald-100 border-2 border-black p-3.5 rounded-md shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
                      <span className="text-[10px] font-extrabold text-emerald-900 uppercase tracking-wider block mb-2">
                        Proposed Revised Paper Text
                      </span>
                      <pre className="whitespace-pre-wrap text-black font-bold text-[11px] leading-relaxed">
                        {impact.suggested_text || section.text}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
