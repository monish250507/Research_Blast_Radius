# PaperBlast: Project Summary Writeup

> **Submission Summary** (Under 200 Words)

```text
Problem: Machine learning codebases and paper manuscripts rapidly desynchronize during research iteration. Hyperparameter changes (like LoRA rank r or loss scaling tau) silently invalidate paper parameter budgets, math formulations, and benchmark tables, causing reproducibility failures and broken peer reviews.

Agent Architecture: PaperBlast uses a 3-agent pipeline over a real-time bipartite AST graph G = (V_code ∪ V_paper, E_deps):
1. Code AST Agent (codeParser.js): Shallow-clones repositories to index line-level AST symbols and functions.
2. Manuscript Analyst Agent (paperParser.js): Extracts structural sections, equations, and tables.
3. Skeptic Verification Arbiter Agent (impactEngine.js): Evaluates blast radius, reconciles section IDs, guarantees complete sentence integrity, and synthesizes side-by-side LaTeX diffs.

Evidence & Data Sources: Real-time public GitHub source code (.py, .js, .ts) via shallow git cloning, and manuscript documents (PDFs via pdf-parse, DOCX via mammoth, LaTeX, and TXT).

Expected Impact: Eliminates manual paper-code proofreading, prevents peer-review rejections due to stale claims, and guarantees 100% mathematical lockstep between open-source code and published papers.
```

---

### Project Links:
- **Live Production URL**: [https://paperblast.vercel.app](https://paperblast.vercel.app)
- **YouTube Demo Video**: [https://youtu.be/iAgQBcwuMZU](https://youtu.be/iAgQBcwuMZU?si=WBNU0XGO803-UskE)
- **GitHub Repository**: [https://github.com/monish250507/Research_Blast_Radius](https://github.com/monish250507/Research_Blast_Radius)
