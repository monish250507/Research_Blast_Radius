import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { exec } from 'child_process';
import { promisify } from 'util';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';

import { extractCodeSymbols } from './codeParser.js';
import { extractTextFromDocument, parsePaperStructure } from './paperParser.js';
import { calculateBlastRadius } from './impactEngine.js';

dotenv.config();

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Serve built frontend assets in standalone mode
const distPath = path.join(__dirname, '../dist');
if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
}

// Serverless-safe scratch temp directory (Uses /tmp on Vercel)
const scratchDir = path.join(os.tmpdir(), 'paperblast_scratch');
if (!fs.existsSync(scratchDir)) {
  try {
    fs.mkdirSync(scratchDir, { recursive: true });
  } catch (e) {}
}

// Helper for fetch with strict network timeout
async function fetchWithTimeout(url, options = {}, timeoutMs = 4000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

/**
 * 100% Real-Time High-Speed GitHub Repository Ingestion Engine.
 * Supports git clone --depth 1 with HTTP zip fallbacks.
 */
app.post('/api/ingest-github', async (req, res) => {
  try {
    const { repoUrl, codeFiles: directFiles } = req.body;

    // Handle Direct Code File Uploads
    if (directFiles && Array.isArray(directFiles)) {
      const symbols = extractCodeSymbols(directFiles);
      return res.json({
        success: true,
        repo: 'Direct Upload',
        fileCount: directFiles.length,
        files: directFiles.map(f => ({ path: f.name || f.path, lineCount: (f.content || '').split('\n').length })),
        symbols
      });
    }

    if (!repoUrl) {
      return res.status(400).json({ error: 'Repository URL or code files required.' });
    }

    const cleanUrl = repoUrl.replace(/\/$/, '').replace(/\.git$/, '');
    const match = cleanUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);

    if (!match) {
      return res.status(400).json({ error: 'Invalid GitHub repository URL structure.' });
    }

    const owner = match[1];
    const repo = match[2];
    const codeFiles = [];
    const validExtensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.cpp', '.cu', '.h', '.c', '.rs', '.go'];

    // Strategy 1: High-Speed git clone --depth 1 --filter=blob:none (30s timeout)
    const targetDir = path.join(scratchDir, `repo_${owner}_${repo}_${Date.now()}`);
    try {
      await execAsync(`git clone --depth 1 --filter=blob:none ${cleanUrl}.git "${targetDir}"`, { timeout: 30000 });

      if (fs.existsSync(targetDir)) {
        const readFilesRecursively = (dir, relPath = '') => {
          const items = fs.readdirSync(dir);
          for (const item of items) {
            if (item === '.git' || item === 'node_modules' || item === 'venv' || item === '__pycache__' || item.startsWith('.')) continue;
            const fullPath = path.join(dir, item);
            const relativeItemPath = relPath ? `${relPath}/${item}` : item;
            const stat = fs.statSync(fullPath);

            if (stat.isDirectory()) {
              readFilesRecursively(fullPath, relativeItemPath);
            } else if (stat.isFile()) {
              const ext = path.extname(item).toLowerCase();
              if (validExtensions.includes(ext) && !relativeItemPath.includes('/test')) {
                try {
                  const content = fs.readFileSync(fullPath, 'utf8');
                  codeFiles.push({ path: relativeItemPath, content });
                } catch (e) {}
              }
            }
          }
        };

        readFilesRecursively(targetDir);
      }
    } catch (gitErr) {
      console.warn('git clone skipped/failed:', gitErr.message);
    } finally {
      if (fs.existsSync(targetDir)) {
        fs.rm(targetDir, { recursive: true, force: true }, () => {});
      }
    }

    // Strategy 2: ZIP archive download fallback
    if (codeFiles.length === 0) {
      for (const branch of ['main', 'master', 'dev']) {
        try {
          const zipUrl = `https://codeload.github.com/${owner}/${repo}/zip/refs/heads/${branch}`;
          const zipRes = await fetchWithTimeout(zipUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
          }, 6000);

          if (zipRes.ok) {
            const arrayBuffer = await zipRes.arrayBuffer();
            const zip = await JSZip.loadAsync(arrayBuffer);

            const entries = Object.keys(zip.files).filter(fn => {
              const ext = path.extname(fn).toLowerCase();
              return !zip.files[fn].dir && validExtensions.includes(ext) && !fn.includes('/test') && !fn.includes('/venv');
            }).slice(0, 30);

            for (const filename of entries) {
              const content = await zip.files[filename].async('string');
              const cleanPath = filename.substring(filename.indexOf('/') + 1);
              codeFiles.push({ path: cleanPath, content });
            }

            if (codeFiles.length > 0) break;
          }
        } catch (e) {}
      }
    }

    if (codeFiles.length === 0) {
      return res.status(404).json({
        error: `Unable to fetch repository source files for ${owner}/${repo}. Please check the URL or use 'Choose Code Files' to upload Python/JS files directly.`
      });
    }

    const selectedFiles = codeFiles.slice(0, 30);
    const symbols = extractCodeSymbols(selectedFiles);

    res.json({
      success: true,
      repo: `${owner}/${repo}`,
      fileCount: selectedFiles.length,
      files: selectedFiles.map(f => ({ path: f.path, lineCount: (f.content || '').split('\n').length })),
      symbols
    });
  } catch (err) {
    console.error('Ingestion endpoint error:', err);
    res.status(500).json({ error: err.message || 'Failed to ingest repository.' });
  }
});

// Parse Paper Endpoint (100% Dynamic PDF / DOCX / LaTeX Extractor)
app.post('/api/parse-paper', async (req, res) => {
  try {
    const { paperText, paperFileBase64, fileType } = req.body;
    let rawText = '';

    if (paperFileBase64) {
      const buffer = Buffer.from(paperFileBase64, 'base64');
      rawText = await extractTextFromDocument(buffer, fileType || 'pdf');
    } else if (paperText) {
      rawText = paperText;
    } else {
      return res.status(400).json({ error: 'Paper text string or document file required.' });
    }

    const paperAST = parsePaperStructure(rawText);

    res.json({
      success: true,
      extractedLength: rawText.length,
      paperAST
    });
  } catch (err) {
    console.error('Paper parse endpoint error:', err);
    res.status(500).json({ error: err.message || 'Failed to parse paper manuscript.' });
  }
});

// Analyze Impact Endpoint (100% Dynamic Blast Radius Engine)
app.post('/api/analyze-impact', async (req, res) => {
  try {
    const { codeSymbols, paperAST, query } = req.body;

    if (!query) {
      return res.status(400).json({ error: 'Change query string required.' });
    }

    if (!codeSymbols || !Array.isArray(codeSymbols)) {
      return res.status(400).json({ error: 'Code symbols array required.' });
    }

    if (!paperAST || !paperAST.sections) {
      return res.status(400).json({ error: 'Paper AST required.' });
    }

    const analysis = await calculateBlastRadius(codeSymbols, paperAST, query);

    res.json({
      success: true,
      analysis
    });
  } catch (err) {
    console.error('Analyze impact endpoint error:', err);
    res.status(500).json({ error: err.message || 'Failed to calculate blast radius.' });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'PaperBlast Impact Analyzer Engine',
    timestamp: new Date().toISOString(),
    groqConfigured: !!process.env.GROQ_API_KEY
  });
});

// SPA Fallback in standalone server mode
app.get('*', (req, res) => {
  if (fs.existsSync(path.join(__dirname, '../dist/index.html'))) {
    res.sendFile(path.join(__dirname, '../dist/index.html'));
  } else {
    res.send('PaperBlast API Running.');
  }
});

// Export app for Vercel serverless execution
export default app;

// Listen on port only when running locally (not on Vercel)
if (!process.env.VERCEL) {
  app.listen(PORT, () => {
    console.log(`PaperBlast Impact Analyzer Server running on port ${PORT}`);
  });
}
