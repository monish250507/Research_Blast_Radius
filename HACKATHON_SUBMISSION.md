# PaperBlast: Hackathon Submission Copy-Paste Kit

> **Project Name**: PaperBlast: Research Code & Paper Impact Analyzer  
> **Tagline**: Multi-Agent Bipartite Program AST & Manuscript Blast Radius Engine  
> **Live Web Application**: [https://paperblast.vercel.app](https://paperblast.vercel.app)  
> **YouTube Demo Video**: [https://youtu.be/iAgQBcwuMZU](https://youtu.be/iAgQBcwuMZU?si=WBNU0XGO803-UskE)  
> **GitHub Repository**: [https://github.com/monish250507/Research_Blast_Radius](https://github.com/monish250507/Research_Blast_Radius)  

---

## 📌 Section 1: Vision Statement (Under 256 Characters Limit)

```text
PaperBlast bridges open-source research code and paper manuscripts. Using a multi-agent bipartite AST graph engine, it automatically calculates the "Blast Radius" of code parameter changes on paper sections and math equations, ensuring trustworthy research.
```

---

## 📌 Section 2: Project Tagline & Quick Pitch

```text
PaperBlast: An automated multi-agent AI system that connects GitHub codebases with research paper manuscripts. It constructs a real-time bipartite AST graph to calculate the exact "Blast Radius" of code parameter changes on paper sections, equations, and tables, synthesizing side-by-side LaTeX diffs.
```

---

## 📌 Section 3: In-Depth Project Description (Detailed & Engaging)

```text
### 1. The Core Research Integrity Problem & Real-World Impact
In contemporary artificial intelligence, machine learning, and computational sciences, open-source software implementations and peer-reviewed academic manuscripts suffer from chronic, dangerous desynchronization. During the active lifecycle of a research project—whether preparing a camera-ready submission, responding to peer-review feedback, or maintaining an open-source library post-publication—codebases undergo continuous modification. Developers and researchers routinely alter hyperparameters (e.g., changing Low-Rank Adaptation rank r from 4 to 8, adjusting temperature scaling parameter tau from 0.07 to 0.01 in contrastive learning loss, modifying attention window block sizes in FlashAttention, or tweaking learning rate decay schedules).

However, scientific paper manuscripts are static, monolithic text files. When developers modify code logic or parameters, they frequently fail to update corresponding manuscript sections. For example, Section 3 ("Methodology") may explicitly claim a specific trainable parameter budget derived from r=4, or Section 4 ("Theoretical Bounds") may rely on a mathematical loss formulation that assumes a specific temperature hyperparameter value. When code changes silently invalidate these manuscript claims, severe consequences follow:
- Mathematical & Conceptual Contradictions: Equations published in the paper no longer match the loss functions or tensor transformations executed in code.
- Broken Peer Reviews & Manuscript Rejections: Reviewers detect discrepancies between reported parameter budgets or equations and the provided code repository.
- Scientific Reproducibility Crisis: External researchers attempting to reproduce published benchmark results fail because the code implementation has drifted from the manuscript's reported methodologies.
- Manual Verification Bottleneck: Manually proofreading a 15-page LaTeX paper against 5,000 lines of PyTorch or JavaScript code after every minor code refactor requires hours of error-prone, exhausting manual effort.

### 2. Core Innovation: Bipartite Program AST & Manuscript Reachability Graph
PaperBlast automates code-to-paper synchronization by constructing a real-time mathematical Bipartite Program AST & Manuscript Reachability Graph:

G = (V_code ∪ V_paper, E_deps)

Graph Formulation Components:
- Code AST Nodes (V_code): Represents line-level program variables, hyperparameter assignments, function signatures, class declarations, and exact file anchors extracted directly from Python (.py) and JavaScript/TypeScript (.js, .ts) source files.
- Manuscript AST Nodes (V_paper): Represents structural section headings (\section{}, \subsection{}), LaTeX equation environments (\begin{equation}), benchmarking tables, and numerical claim text snippets extracted from PDF, DOCX, or LaTeX files.
- Directed Reachability Edges (E_deps): Represents program symbol references, mathematical variable equivalences, parameter dependency propagation paths, and query keyword alignments across code and manuscript text.

When a researcher or developer inputs a proposed code mutation or what-if parameter change query (e.g., "What happens if I change the temperature scaling parameter tau from 0.07 to 0.01 in the contrastive loss?"), PaperBlast evaluates reachability across the bipartite graph, calculating the exact "Blast Radius", assigning risk ratings (CRITICAL, HIGH, MAJOR, MINOR) to affected manuscript sections, and synthesizing side-by-side proposed LaTeX text revisions.

### 3. Multi-Agent Collaborative Architecture & Protocol
PaperBlast implements an autonomous 3-Agent Collaborative Pipeline with auditable state tracing and error-recovery fallbacks:

- Agent 1: Code AST Dependency Agent (codeParser.js)
  Performs real-time shallow git cloning (git clone --depth 1 --filter=blob:none) into isolated temporary storage (/tmp) to bypass GitHub API rate limits. It executes Abstract Syntax Tree (AST) parsing and regular expression symbol extraction to index line-level variables, functions, hyperparameters, and file anchors across source files.

- Agent 2: Manuscript Impact Analyst Agent (paperParser.js)
  Parses research PDFs (via pdf-parse), Word DOCX files (via mammoth), LaTeX files (.tex), and raw text excerpts into a structured Document AST containing section hierarchies, equation environments, table cells, and numerical claims.

- Agent 3: Skeptic Verification Arbiter Agent (impactEngine.js)
  Cross-references proposed code mutations against indexed AST symbols and paper sections. It reconciles section ID keys against paperAST.sections, enforces strict sentence boundary truncation (preventing incomplete broken text), evaluates risk levels, and executes deterministic local AST reachability fallbacks to guarantee zero AI hallucinations.

### 4. End-to-End System Workflow & User Experience
1. Code AST Symbol Indexing: User enters any public GitHub repository URL (e.g., https://github.com/openai/CLIP) or uploads local code files (.py, .js, .ts). Agent 1 shallow-clones the repository and indexes line-level AST symbols.
2. Document AST Parsing: User uploads any research paper PDF (e.g., cli_compressed.pdf), Word DOCX, or LaTeX file. Agent 2 parses structural sections, equation environments, and text snippets.
3. What-If Query Launcher: User inputs a proposed parameter change query (e.g., "What happens if I change the temperature scaling parameter tau from 0.07 to 0.01 in the contrastive loss?").
4. Real-Time Blast Radius Calculation: Agent 3 computes reachability across the bipartite graph, assigning an Overall Blast Radius Score (0-100%) and section risk ratings.
5. Interactive Revisions & Audit Report Export: Users review side-by-side LaTeX text diffs (Current Paper Text vs Proposed Revised Text) and export complete auditable analysis states as downloadable .json reports.

### 5. Hardware-Accelerated Cost Efficiency & System Specifications
- Cost-Efficiency Engineering: Runs on Groq Temperature 0.0 LPU hardware inference engines capped under 1,500 prompt tokens for zero cost ($0.00 estimated cost per analysis).
- Neobrutalist UI Design: Built with React 18, Vite, Tailwind CSS v4, and a Neobrutalist design system featuring a soft ice-blue (#dbeafe) canvas, crisp white cards, 2px solid black borders, and 4px hard offset drop shadows.
- Production Serverless Architecture: Deployed live on Vercel Production at https://paperblast.vercel.app with serverless Node.js API functions.
```

---

## 📌 Section 4: All-in-One Master Block (For Single Description Fields)

```text
PAPERBLAST: MULTI-AGENT BIPARTITE PROGRAM AST & MANUSCRIPT BLAST RADIUS ENGINE

Overview & Real-World Impact:
PaperBlast is a multi-agent AI system that bridges open-source research codebases and academic paper manuscripts to solve the critical code-paper desynchronization problem. Built for the Research Agents Hack sprint, it constructs a real-time Bipartite Program AST Reachability Graph G = (V_code ∪ V_paper, E_deps) to calculate the exact "Blast Radius" of code changes on paper sections, math equations, and benchmarking tables.

When AI developers modify code hyperparameters (e.g., changing LoRA rank r from 4 to 8, adjusting temperature scaling parameter tau from 0.07 to 0.01, or modifying learning rates), paper manuscripts remain static text files. Developers forget that Section 3 claims a specific parameter budget or Section 4 relies on an exact math loss formulation. This leads to silent paper invalidations, broken equations, peer-review rejections, and reproducibility crises.

How PaperBlast Solves It:
Given any proposed code mutation or change query (e.g., "What happens if I change the temperature scaling parameter tau from 0.07 to 0.01 in the contrastive loss?"), PaperBlast computes reachability across the bipartite graph, assigning an overall Blast Radius Score (0-100%) and section risk ratings (CRITICAL to MINOR). It visualizes interactive lineage flows and synthesizes side-by-side proposed LaTeX revisions.

3-Agent Collaborative Pipeline:
1. Code AST Dependency Agent (codeParser.js): Shallow-clones GitHub repositories (git clone --depth 1 --filter=blob:none) to index line-level AST symbols, variables, functions, and file anchors across Python and JavaScript files.
2. Manuscript Impact Analyst Agent (paperParser.js): Parses research PDFs (via pdf-parse), Word DOCX (via mammoth), and LaTeX files into structural section hierarchies, equations, and tables.
3. Skeptic Verification Arbiter Agent (impactEngine.js): Cross-references code AST symbols against paper sections, reconciles section IDs, guarantees complete sentence integrity, and executes deterministic local AST fallbacks to eliminate AI hallucinations.

Quick Demo Benchmark (Try It Yourself):
- GitHub Repository: https://github.com/openai/CLIP
- Research Paper PDF: cli_compressed.pdf (included in repository)
- Change Query: "What happens if I change the temperature scaling parameter tau from 0.07 to 0.01 in the contrastive loss?"

Technical Stack & Cost Efficiency:
- Hardware-accelerated Groq LPU inference ($0.00 estimated cost).
- React 18, Vite, Tailwind CSS v4 with a Neobrutalist design system (#dbeafe canvas, 2px borders, 4px drop shadows).
- Serverless Express Node.js architecture deployed on Vercel.

Submission Links:
- Live Web Application: https://paperblast.vercel.app
- YouTube Demo Video: https://youtu.be/iAgQBcwuMZU
- GitHub Repository: https://github.com/monish250507/Research_Blast_Radius
```

---

## 📌 Section 5: Judging Criteria Summary Checklist

| Criteria | Score Target | Evidence in Submission |
| :--- | :---: | :--- |
| **Research Utility** | **30%** | Solves paper-code desynchronization by computing the exact Blast Radius of code mutations on manuscript text and equations. |
| **Agent Collaboration** | **25%** | 3 specialized agents (`Code AST Agent`, `Manuscript Analyst`, `Skeptic Arbiter`) passing formal state in a bipartite graph. |
| **Working Demo** | **20%** | 100% operational live on Vercel at **https://paperblast.vercel.app** with video walkthrough at **https://youtu.be/iAgQBcwuMZU**. |
| **Cost Efficiency** | **15%** | Token-capped prompts (< 1,500 tokens) running on hardware-accelerated Groq Temperature 0.0 LPUs ($0.00 cost). |
| **Originality** | **10%** | Bipartite graph reachability formulation $\mathcal{G} = (V_{\text{code}} \cup V_{\text{paper}}, E_{\text{deps}})$ with downloadable JSON audit reports. |
