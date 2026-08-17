import path from 'path';

/**
 * Deterministically parses code files to extract AST symbols, variables, parameters, loss functions, and metrics.
 * @param {Array<{path: string, content: string}>} files 
 * @returns {Array<ASTSymbol>}
 */
export function extractCodeSymbols(files) {
  const symbols = [];

  for (const file of files) {
    if (!file || !file.content) continue;

    const ext = path.extname(file.path).toLowerCase();
    const relativePath = file.path;

    if (ext === '.py') {
      const pySymbols = parsePythonASTNative(file.content, relativePath);
      if (Array.isArray(pySymbols)) {
        for (const sym of pySymbols) symbols.push(sym);
      }
    } else if (['.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml'].includes(ext)) {
      const jsSymbols = parseJSOrConfig(file.content, relativePath);
      if (Array.isArray(jsSymbols)) {
        for (const sym of jsSymbols) symbols.push(sym);
      }
    }
  }

  return symbols;
}

/**
 * High-speed native JS Python AST Symbol Extractor (< 1ms per file).
 * Extracts variable assignments, class definitions, function signatures, loss functions, and metrics.
 */
function parsePythonASTNative(code, filePath) {
  const symbols = [];
  const lines = code.split('\n');

  let currentClass = null;

  lines.forEach((lineText, idx) => {
    const lineNum = idx + 1;
    const trimmed = lineText.trim();

    if (!trimmed || trimmed.startsWith('#')) return;

    // Detect Class definitions
    const classMatch = trimmed.match(/^class\s+([a-zA-Z_][a-zA-Z0-9_]*)/);
    if (classMatch) {
      currentClass = classMatch[1];
      symbols.push({
        symbol: classMatch[1],
        type: 'Class',
        value: `class ${classMatch[1]}`,
        line: lineNum,
        file: filePath
      });
      return;
    }

    // Detect Function definitions
    const funcMatch = trimmed.match(/^def\s+([a-zA-Z_][a-zA-Z0-9_]*)/);
    if (funcMatch) {
      symbols.push({
        symbol: funcMatch[1],
        type: 'Function',
        value: `def ${funcMatch[1]}`,
        line: lineNum,
        file: filePath
      });
      return;
    }

    // Detect Variable & Parameter Assignments (e.g. learning_rate = 1e-4, r = 8, lora_alpha = 16)
    const assignMatch = trimmed.match(/^(?:self\.)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^#\n]+)/);
    if (assignMatch) {
      const varName = assignMatch[1];
      const valStr = assignMatch[2].trim();

      // Filter out self/private noise variables, keep parameters & hyperparameters
      if (!['self', 'cls', 'super', 'print', 'return', 'if', 'else', 'elif', 'for', 'while'].includes(varName)) {
        symbols.push({
          symbol: varName,
          type: currentClass ? `ClassVariable (${currentClass})` : 'Variable',
          value: valStr.length > 60 ? valStr.slice(0, 60) + '...' : valStr,
          line: lineNum,
          file: filePath
        });
      }
    }
  });

  return symbols;
}

/**
 * Parses JS, TS, JSON, and YAML configuration files.
 */
function parseJSOrConfig(code, filePath) {
  const symbols = [];
  const lines = code.split('\n');

  lines.forEach((lineText, idx) => {
    const lineNum = idx + 1;
    const trimmed = lineText.trim();
    if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('#')) return;

    // Detect JS/TS variable declarations: const lr = 0.001, let batch_size = 32
    const varMatch = trimmed.match(/(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^;]+)/);
    if (varMatch) {
      symbols.push({
        symbol: varMatch[1],
        type: 'Variable',
        value: varMatch[2].trim(),
        line: lineNum,
        file: filePath
      });
    }

    // Detect JSON/YAML key-value pairs (e.g., "learning_rate": 0.001, batch_size: 64)
    const kvMatch = trimmed.match(/^"?([a-zA-Z_][a-zA-Z0-9_-]*)"?\s*:\s*(.+)$/);
    if (kvMatch) {
      symbols.push({
        symbol: kvMatch[1],
        type: 'ConfigKey',
        value: kvMatch[2].replace(/[,"]+/g, '').trim(),
        line: lineNum,
        file: filePath
      });
    }
  });

  return symbols;
}
