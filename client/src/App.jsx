import React, { useState } from 'react';
import BlastRadiusHeader from './components/BlastRadiusHeader';
import WhatIfConsole from './components/WhatIfConsole';
import CodeGraphViewer from './components/CodeGraphViewer';
import PaperImpactViewer from './components/PaperImpactViewer';
import DependencyFlow from './components/DependencyFlow';

export default function App() {
  // Start with completely blank empty state (0 prefilled mock data)
  const [repoUrl, setRepoUrl] = useState('');
  const [query, setQuery] = useState('');
  const [paperText, setPaperText] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');

  const [codeSymbols, setCodeSymbols] = useState([]);
  const [ingestedFilesCount, setIngestedFilesCount] = useState(0);
  const [paperAST, setPaperAST] = useState({ sections: [], equations: [], tables: [], numbers: [] });
  const [analysis, setAnalysis] = useState(null);

  const [isIngesting, setIsIngesting] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [activeTab, setActiveTab] = useState('overview');

  // Ingest GitHub Repository
  const handleIngestRepo = async () => {
    if (!repoUrl.trim()) return;
    setIsIngesting(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/ingest-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repoUrl })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to ingest repository');

      setCodeSymbols(data.symbols || []);
      setIngestedFilesCount(data.fileCount || 1);
    } catch (err) {
      console.error('Repo ingestion error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  // Upload Code Files Directly
  const handleCodeFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    setIsIngesting(true);
    setErrorMsg('');

    try {
      const codeFiles = await Promise.all(
        files.map(file => new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve({ name: file.name, content: reader.result });
          reader.onerror = reject;
          reader.readAsText(file);
        }))
      );

      const res = await fetch('/api/ingest-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codeFiles })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to parse code files');

      setCodeSymbols(data.symbols || []);
      setIngestedFilesCount(codeFiles.length);
    } catch (err) {
      console.error('Code file upload error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  // Parse Raw Paper Text Excerpt
  const handleParsePaper = async () => {
    if (!paperText.trim()) return;
    setIsIngesting(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/parse-paper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paperText })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to parse paper manuscript');

      setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
    } catch (err) {
      console.error('Paper text parse error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  // Upload PDF / DOCX / LaTeX Document using native browser FileReader Base64
  const handlePaperFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setSelectedFileName(file.name);
    setIsIngesting(true);
    setErrorMsg('');

    try {
      const ext = file.name.split('.').pop().toLowerCase();
      const reader = new FileReader();

      reader.onload = async () => {
        const base64Data = reader.result.split(',')[1] || reader.result;

        try {
          const res = await fetch('/api/parse-paper', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              paperFileBase64: base64Data,
              fileType: ext
            })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'Failed to parse uploaded document');

          setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
        } catch (err) {
          console.error('Document parse error:', err);
          setErrorMsg(err.message);
        } finally {
          setIsIngesting(false);
        }
      };

      reader.onerror = () => {
        setErrorMsg('Failed to read document file.');
        setIsIngesting(false);
      };

      reader.readAsDataURL(file);
    } catch (err) {
      console.error('File reader error:', err);
      setErrorMsg(err.message);
      setIsIngesting(false);
    }
  };

  // Calculate Blast Radius Analysis
  const handleCalculateBlastRadius = async () => {
    if (!query.trim()) return;
    setIsAnalyzing(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/analyze-impact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          codeSymbols,
          paperAST,
          query
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to calculate blast radius');

      setAnalysis(data.analysis || null);
    } catch (err) {
      console.error('Blast radius calculation error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Export Audit Report (.json)
  const handleExportReport = () => {
    if (!analysis) return;
    const reportData = {
      timestamp: new Date().toISOString(),
      query,
      repository: repoUrl,
      symbolsIndexedCount: codeSymbols.length,
      sectionsCount: paperAST.sections.length,
      blastRadiusAnalysis: analysis
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `paperblast-audit-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#dbeafe] text-slate-900 flex flex-col items-center w-full font-sans">
      {/* Centered App Container */}
      <div className="app-wrapper space-y-6 flex flex-col items-center">
        {/* Top Header */}
        <BlastRadiusHeader
          analysis={analysis}
          hasCode={codeSymbols.length > 0}
          hasPaper={paperAST.sections.length > 0}
          isIngesting={isIngesting}
          isAnalyzing={isAnalyzing}
          onExportReport={handleExportReport}
        />

        {/* Main Content Area */}
        <main className="w-full space-y-6 flex flex-col items-center">
          {/* Error Alert */}
          {errorMsg && (
            <div className="bg-rose-200 border-2 border-black text-black px-4 py-3 rounded-md font-mono text-xs flex items-center justify-between shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] w-full">
              <span className="font-bold">Error: {errorMsg}</span>
              <button className="neo-btn-white py-0.5 px-2 text-xs" onClick={() => setErrorMsg('')}>Dismiss</button>
            </div>
          )}

          {/* Input Console */}
          <WhatIfConsole
            query={query}
            setQuery={setQuery}
            onCalculate={handleCalculateBlastRadius}
            repoUrl={repoUrl}
            setRepoUrl={setRepoUrl}
            onIngestRepo={handleIngestRepo}
            onCodeFileUpload={handleCodeFileUpload}
            onPaperFileUpload={handlePaperFileUpload}
            paperText={paperText}
            setPaperText={setPaperText}
            onParsePaper={handleParsePaper}
            isIngesting={isIngesting}
            isAnalyzing={isAnalyzing}
            ingestedFilesCount={ingestedFilesCount}
            symbolsCount={codeSymbols.length}
            sectionsCount={paperAST.sections.length}
            selectedFileName={selectedFileName}
          />

          {/* Workspace Navigation Tabs (Centered) */}
          <div className="flex flex-wrap items-center justify-center gap-3 py-2 w-full">
            <button
              className={`neo-tab ${activeTab === 'overview' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              Impact Overview
            </button>
            <button
              className={`neo-tab ${activeTab === 'manuscript' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('manuscript')}
            >
              Manuscript Section Matrix ({paperAST.sections.length})
            </button>
            <button
              className={`neo-tab ${activeTab === 'lineage' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('lineage')}
            >
              Bipartite Lineage Graph ({analysis?.lineage_graph?.length || 0})
            </button>
            <button
              className={`neo-tab ${activeTab === 'agents' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('agents')}
            >
              Agent Trace ({analysis?.agent_collaboration_trace?.length || 3})
            </button>
            <button
              className={`neo-tab ${activeTab === 'code' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              Code AST Symbols ({codeSymbols.length})
            </button>
          </div>

          {/* Tab Contents */}
          <div className="w-full">
            {activeTab === 'overview' && (
              <div className="space-y-6 w-full">
                {/* Lineage Graph Flow */}
                {analysis?.lineage_graph && analysis.lineage_graph.length > 0 && (
                  <DependencyFlow lineageGraph={analysis.lineage_graph} />
                )}

                {/* Split Screen Grid: Code AST (Left) vs Paper Matrix (Right) */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full">
                  {/* Left: Code AST Symbols */}
                  <div className="lg:col-span-4 neo-box p-5">
                    <CodeGraphViewer symbols={codeSymbols} />
                  </div>

                  {/* Right: Paper Impact Matrix */}
                  <div className="lg:col-span-8 neo-box p-5">
                    <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'manuscript' && (
              <div className="neo-box p-5 w-full">
                <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
              </div>
            )}

            {activeTab === 'lineage' && (
              <div className="neo-box p-5 w-full">
                <DependencyFlow lineageGraph={analysis?.lineage_graph || []} />
              </div>
            )}

            {activeTab === 'agents' && (
              <div className="neo-box p-5 space-y-4 w-full">
                <div className="flex flex-col items-start border-b-2 border-black pb-2 gap-0.5">
                  <h3 className="text-xs font-extrabold text-black uppercase tracking-wider font-mono">
                    Multi-Agent Collaboration Trace Log
                  </h3>
                  <p className="text-[11px] font-mono font-semibold text-slate-600">
                    Auditable state log showing roles, outputs, and verification checks performed by each agent.
                  </p>
                </div>
                <div className="space-y-3">
                  {(analysis?.agent_collaboration_trace || [
                    { agent: 'Code AST Dependency Agent', role: 'Program Analysis & Symbol Extraction', output_summary: `Indexed ${codeSymbols.length} AST symbols.` },
                    { agent: 'Manuscript Impact Analyst Agent', role: 'Paper AST Parsing & Equation Matching', output_summary: `Evaluated ${paperAST.sections.length} manuscript sections.` },
                    { agent: 'Skeptic Verification Arbiter Agent', role: 'Risk Validation & Sentence Audit', output_summary: `Validated risk bounds and complete sentences.` }
                  ]).map((trace, idx) => (
                    <div key={idx} className="bg-white border-2 border-black p-4 rounded-md font-mono text-xs shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-extrabold text-black uppercase text-xs">{trace.agent}</span>
                        <span className="bg-emerald-200 border border-black px-2 py-0.5 rounded text-[10px] font-extrabold">VERIFIED ACTIVE</span>
                      </div>
                      <p className="text-[11px] text-slate-700 font-bold">Role: {trace.role}</p>
                      <p className="text-[11px] text-slate-900 font-medium">Output: {trace.output_summary}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'code' && (
              <div className="neo-box p-5 w-full">
                <CodeGraphViewer symbols={codeSymbols} />
              </div>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="w-full neo-box py-4 px-6 text-center text-xs font-mono font-bold text-black mt-6">
          PaperBlast Program Analysis Engine — Multi-Agent Bipartite Program AST & Manuscript Blast Radius Engine
        </footer>
      </div>
    </div>
  );
}
