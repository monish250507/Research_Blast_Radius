import pdfParse from 'pdf-parse';
import mammoth from 'mammoth';
import JSZip from 'jszip';

/**
 * Extracts raw text from PDF, DOCX, LaTeX, Markdown, or raw text buffers/strings.
 */
export async function extractTextFromDocument(inputBufferOrString, fileType = 'txt') {
  if (typeof inputBufferOrString === 'string') {
    return inputBufferOrString;
  }

  const buffer = Buffer.isBuffer(inputBufferOrString) ? inputBufferOrString : Buffer.from(inputBufferOrString);
  const type = (fileType || '').toLowerCase();

  if (type === 'pdf') {
    try {
      const parsed = await pdfParse(buffer);
      return parsed.text || '';
    } catch (err) {
      console.warn('pdf-parse failed, returning raw string fallback:', err.message);
      return buffer.toString('utf-8');
    }
  }

  if (type === 'docx') {
    try {
      const result = await mammoth.extractRawText({ buffer });
      if (result.value) return result.value;
    } catch (err) {
      console.warn('mammoth parsing failed, trying JSZip fallback:', err.message);
    }

    try {
      const zip = await JSZip.loadAsync(buffer);
      const docXml = await zip.file('word/document.xml')?.async('string');
      if (docXml) {
        return docXml.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      }
    } catch (zipErr) {
      console.warn('JSZip docx fallback failed:', zipErr.message);
    }
  }

  return buffer.toString('utf-8');
}

/**
 * Structural paper parser for LaTeX (.tex), Markdown (.md), PDF text, and raw text.
 */
export function parsePaperStructure(rawText) {
  if (!rawText || typeof rawText !== 'string') {
    return { rawText: '', sections: [], equations: [], tables: [], numbers: [] };
  }

  // Strip LaTeX comments
  const cleanText = rawText.replace(/^[ \t]*%[^\n]*/gm, '');

  const sections = extractSections(cleanText);
  const equations = extractEquations(cleanText);
  const tables = extractTables(cleanText);
  const numbers = extractNumericalClaims(cleanText);

  return {
    rawText: cleanText,
    sections,
    equations,
    tables,
    numbers
  };
}

/**
 * Strict scientific section extractor for PDF text, LaTeX, and Markdown.
 * Strictly limits headings to actual research paper section titles (Abstract, Introduction, Method, Results, etc.).
 * Table headers, numbers, and parameters (e.g. Epochs, Trainable) are NEVER treated as section titles.
 */
function extractSections(text) {
  const sections = [];
  const lines = text.split('\n');

  let currentSection = {
    id: 'sec-1-abstract',
    title: 'Abstract',
    content: [],
    startLine: 1,
    endLine: 1
  };

  // Strictly match ONLY valid scientific research paper section headings (Must match full line, no table numbers concatenated!)
  const canonicalHeadingRegex = /^(?:(?:\d+\.|\d+\.\d+|\d+)\s+)?(Abstract|Introduction|Related Work|Background|Problem Formulation|Methodology|Method|Methods|Model Architecture|Experimental Setup|Experiments|Evaluation|Results|Discussion|Ablation Study|Conclusion|References|Appendix)\s*$/i;

  const numberedHeadingRegex = /^(?:\d+\.|\d+\.\d+|\d+)\s+[A-Z][A-Za-z\s:-]{2,45}\s*$/;

  lines.forEach((line, idx) => {
    const lineNum = idx + 1;
    const trimmed = line.trim();

    if (!trimmed) {
      currentSection.content.push(line);
      return;
    }

    // 1. LaTeX section match: \section{...}, \subsection{...}
    const texSecMatch = trimmed.match(/\\(section|subsection|subsubsection)\*?\s*\{([^}]+)\}/);
    
    // Clean line without leading Markdown #
    const cleanLine = trimmed.replace(/^#{1,4}\s*/, '');
    
    // 2. Strict standalone section header match (Must match exact heading title line ONLY!)
    const isHeading = texSecMatch || (cleanLine.length < 60 && (canonicalHeadingRegex.test(cleanLine) || numberedHeadingRegex.test(cleanLine)));

    if (isHeading) {
      if (currentSection.content.length > 0) {
        currentSection.endLine = lineNum - 1;
        const bodyText = currentSection.content.join('\n').trim();
        if (bodyText) {
          sections.push({
            ...currentSection,
            text: bodyText
          });
        }
      }

      let title = 'Section';
      if (texSecMatch) title = texSecMatch[2];
      else title = cleanLine;

      // Clean section title
      title = title.replace(/^[\d.]+\s*/, '').trim();
      const secId = `sec-${sections.length + 1}-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

      currentSection = {
        id: secId,
        title: title,
        content: [],
        startLine: lineNum,
        endLine: lineNum
      };
    } else {
      currentSection.content.push(line);
    }
  });

  if (currentSection.content.length > 0) {
    currentSection.endLine = lines.length;
    const bodyText = currentSection.content.join('\n').trim();
    if (bodyText) {
      sections.push({
        ...currentSection,
        text: bodyText
      });
    }
  }

  // Fallback: If no sections were split, return 1 full manuscript section
  if (sections.length === 0) {
    sections.push({
      id: 'sec-1-manuscript-body',
      title: 'Full Manuscript Body',
      content: lines,
      text: text,
      startLine: 1,
      endLine: lines.length
    });
  }

  return sections;
}

/**
 * Extracts LaTeX and Markdown equations.
 */
function extractEquations(text) {
  const equations = [];
  const envRegex = /\\begin\{(equation|align|eqnarray)\*?\}([\s\S]*?)\\end\{\1\*?\}/g;
  let match;
  let eqCount = 1;

  while ((match = envRegex.exec(text)) !== null) {
    equations.push({
      id: `eq-${eqCount}`,
      label: `Equation (${eqCount})`,
      content: match[2].trim(),
      raw: match[0],
      type: match[1]
    });
    eqCount++;
  }

  const displayRegex = /\$\$([\s\S]*?)\$\$/g;
  while ((match = displayRegex.exec(text)) !== null) {
    equations.push({
      id: `eq-${eqCount}`,
      label: `Equation (${eqCount})`,
      content: match[1].trim(),
      raw: match[0],
      type: 'display'
    });
    eqCount++;
  }

  return equations;
}

/**
 * Extracts LaTeX tables and Markdown tables.
 */
function extractTables(text) {
  const tables = [];
  const texTableRegex = /\\begin\{table\*?\}([\s\S]*?)\\end\{table\*?\}/g;
  let match;
  let tabCount = 1;

  while ((match = texTableRegex.exec(text)) !== null) {
    const raw = match[0];
    const captionMatch = raw.match(/\\caption\{([^}]+)\}/);
    const caption = captionMatch ? captionMatch[1] : `Table ${tabCount}`;

    tables.push({
      id: `table-${tabCount}`,
      label: `Table ${tabCount}`,
      caption,
      content: raw,
      type: 'latex'
    });
    tabCount++;
  }

  const mdTableRegex = /(?:\|[^\n]+\|\n)+/g;
  while ((match = mdTableRegex.exec(text)) !== null) {
    const raw = match[0];
    if (raw.includes('|---') || raw.includes('| ---')) {
      tables.push({
        id: `table-${tabCount}`,
        label: `Table ${tabCount}`,
        caption: `Markdown Table ${tabCount}`,
        content: raw,
        type: 'markdown'
      });
      tabCount++;
    }
  }

  return tables;
}

/**
 * Extracts numerical claims from text.
 */
function extractNumericalClaims(text) {
  const claims = [];
  const numRegex = /\b(\d+(?:\.\d+)?%|\d+(?:\.\d+)?e-?\d+|\d+(?:\.\d+)?\s*(?:ms|GB|MB|params|dim|layers|heads|epochs))\b/gi;
  let match;

  while ((match = numRegex.exec(text)) !== null) {
    claims.push({
      value: match[1],
      index: match.index
    });
  }

  return claims;
}
