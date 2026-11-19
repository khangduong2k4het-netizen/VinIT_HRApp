/**
 * Read the text of a .docx in the browser, with no backend change and no
 * third-party document library.
 *
 * A .docx is a ZIP whose `word/document.xml` holds the visible text. Browsers can
 * already inflate raw DEFLATE (`DecompressionStream('deflate-raw')`), so we only
 * need to read the ZIP central directory ourselves, inflate that one entry, and
 * pull the `<w:t>` runs out of the XML. Rendering goes through React nodes, never
 * `innerHTML`, so a CV cannot inject markup into the app.
 *
 * Tables are kept as tables (`w:tbl` → rows and cells, in document order). Student
 * CVs very often put experience in a table, and flattening those cells into a
 * paragraph stream read the columns in the wrong order — one cell per line — so
 * the reviewer compared the wrong row with the criterion. Cell merges keep their
 * column position (`w:gridSpan`), and a header row is marked only when Word marks
 * it (`w:tblHeader`), never guessed.
 *
 * Deliberately limited: this is a reading aid for screening, not a layout engine.
 * Columns, fonts and spacing are still not reproduced, and the original file stays
 * one click away ("Tải CV gốc"). Anything this cannot read (encrypted, or a legacy
 * .doc renamed to .docx) throws, so the caller can say so instead of showing an
 * empty panel.
 */

const LOCAL_HEADER_SIG = 0x04034b50;
const CENTRAL_HEADER_SIG = 0x02014b50;
const END_OF_CENTRAL_DIR_SIG = 0x06054b50;

const WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const DOCUMENT_ENTRY = 'word/document.xml';

type ZipEntry = { name: string; method: number; compressedSize: number; localHeaderOffset: number };

/** One readable piece of the document, in the order Word lays it out. */
export type DocxBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'table'; rows: string[][]; header: boolean };

function findEndOfCentralDirectory(view: DataView): number {
  // The EOCD record is the last 22 bytes plus an optional comment of up to 64 KiB.
  const stop = Math.max(0, view.byteLength - 22 - 0xffff);
  for (let offset = view.byteLength - 22; offset >= stop; offset -= 1) {
    if (view.getUint32(offset, true) === END_OF_CENTRAL_DIR_SIG) return offset;
  }
  return -1;
}

function readZipEntries(view: DataView): ZipEntry[] {
  const eocd = findEndOfCentralDirectory(view);
  if (eocd < 0) throw new Error('DOCX_INVALID');
  const count = view.getUint16(eocd + 10, true);
  let cursor = view.getUint32(eocd + 16, true);
  const entries: ZipEntry[] = [];
  for (let index = 0; index < count; index += 1) {
    if (cursor + 46 > view.byteLength || view.getUint32(cursor, true) !== CENTRAL_HEADER_SIG) break;
    const method = view.getUint16(cursor + 10, true);
    const compressedSize = view.getUint32(cursor + 20, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const localHeaderOffset = view.getUint32(cursor + 42, true);
    const name = new TextDecoder().decode(new Uint8Array(view.buffer, view.byteOffset + cursor + 46, nameLength));
    entries.push({ name, method, compressedSize, localHeaderOffset });
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

function readEntryBytes(view: DataView, entry: ZipEntry): Uint8Array {
  const offset = entry.localHeaderOffset;
  if (view.getUint32(offset, true) !== LOCAL_HEADER_SIG) throw new Error('DOCX_INVALID');
  const nameLength = view.getUint16(offset + 26, true);
  const extraLength = view.getUint16(offset + 28, true);
  const start = offset + 30 + nameLength + extraLength;
  return new Uint8Array(view.buffer, view.byteOffset + start, entry.compressedSize);
}

async function inflateRaw(bytes: Uint8Array): Promise<Uint8Array> {
  if (typeof DecompressionStream === 'undefined') throw new Error('DOCX_UNSUPPORTED');
  const stream = new Blob([bytes as unknown as BlobPart]).stream().pipeThrough(new DecompressionStream('deflate-raw' as CompressionFormat));
  const inflated = await new Response(stream).arrayBuffer();
  return new Uint8Array(inflated);
}

/** One paragraph, tabs and line breaks kept, trailing whitespace trimmed. */
function paragraphText(paragraph: Element): string {
  const walker = (paragraph.ownerDocument as Document).createTreeWalker(paragraph, NodeFilter.SHOW_ELEMENT);
  let text = '';
  for (let node = walker.nextNode() as Element | null; node; node = walker.nextNode() as Element | null) {
    if (node.namespaceURI !== WORD_NS) continue;
    if (node.localName === 't') text += node.textContent || '';
    else if (node.localName === 'tab') text += '\t';
    else if (node.localName === 'br' || node.localName === 'cr') text += '\n';
  }
  return text.replace(/[ \t]+$/u, '');
}

/**
 * Children of a WordprocessingML container, looking inside content-control
 * wrappers (`w:sdt`) that carry text but are not paragraphs themselves.
 */
function blockChildren(container: Element): Element[] {
  const result: Element[] = [];
  for (const child of Array.from(container.children)) {
    if (child.namespaceURI !== WORD_NS) continue;
    if (child.localName === 'sdt' || child.localName === 'sdtContent' || child.localName === 'customXml' || child.localName === 'smartTag') {
      result.push(...blockChildren(child));
    } else {
      result.push(child);
    }
  }
  return result;
}

function wordChild(parent: Element, localName: string): Element | null {
  return Array.from(parent.children).find(child => child.namespaceURI === WORD_NS && child.localName === localName) || null;
}

/** Columns a cell occupies, so a merged cell does not shift the row to the left. */
function gridSpan(cell: Element): number {
  const properties = wordChild(cell, 'tcPr');
  const span = properties ? wordChild(properties, 'gridSpan') : null;
  const value = span ? Number(span.getAttribute('w:val') || span.getAttributeNS(WORD_NS, 'val') || '1') : 1;
  return Number.isFinite(value) && value > 1 ? Math.floor(value) : 1;
}

/** Text of one cell: its paragraphs, in order; a nested table becomes one line per row. */
function cellText(cell: Element): string {
  const parts: string[] = [];
  for (const child of blockChildren(cell)) {
    if (child.localName === 'p') {
      const text = paragraphText(child).trim();
      if (text) parts.push(text);
    } else if (child.localName === 'tbl') {
      for (const row of tableRows(child)) parts.push(row.filter(Boolean).join(' · '));
    }
  }
  return parts.join(' ');
}

function tableRows(table: Element): string[][] {
  const rows: string[][] = [];
  for (const row of Array.from(table.children)) {
    if (row.namespaceURI !== WORD_NS || row.localName !== 'tr') continue;
    const cells: string[] = [];
    for (const cell of Array.from(row.children)) {
      if (cell.namespaceURI !== WORD_NS || cell.localName !== 'tc') continue;
      cells.push(cellText(cell));
      // A merged cell holds the slot of the columns it covers.
      for (let pad = gridSpan(cell) - 1; pad > 0; pad -= 1) cells.push('');
    }
    // A row of empty cells carries no information and would only add a blank line.
    if (cells.some(cell => cell.trim())) rows.push(cells);
  }
  return rows;
}

/** Word marks a repeated header row; the reader follows that, it never guesses. */
function hasHeaderRow(table: Element): boolean {
  const firstRow = Array.from(table.children).find(row => row.namespaceURI === WORD_NS && row.localName === 'tr');
  const properties = firstRow ? wordChild(firstRow, 'trPr') : null;
  return Boolean(properties && wordChild(properties, 'tblHeader'));
}

function xmlToBlocks(xml: string): DocxBlock[] {
  const doc = new DOMParser().parseFromString(xml, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length > 0) throw new Error('DOCX_INVALID');
  const body = doc.getElementsByTagNameNS(WORD_NS, 'body')[0] || doc.documentElement;
  const blocks: DocxBlock[] = [];
  const pushParagraph = (text: string) => {
    // A blank paragraph is a visual gap; keep one, drop the runs of them that
    // Word files carry between/after tables.
    const previous = blocks[blocks.length - 1];
    if (!text.trim() && previous && previous.kind === 'paragraph' && previous.text === '') return;
    blocks.push({ kind: 'paragraph', text });
  };
  for (const child of blockChildren(body)) {
    if (child.localName === 'p') {
      pushParagraph(paragraphText(child));
    } else if (child.localName === 'tbl') {
      const rows = tableRows(child);
      if (rows.length) blocks.push({ kind: 'table', rows, header: hasHeaderRow(child) });
    }
  }
  while (blocks.length) {
    const last = blocks[blocks.length - 1];
    if (last.kind !== 'paragraph' || last.text !== '') break;
    blocks.pop();
  }
  return blocks;
}

/**
 * Readable blocks of a .docx, in document order: paragraphs and tables. Throws
 * DOCX_INVALID for a file that is not a readable ZIP, DOCX_UNSUPPORTED when the
 * browser cannot inflate, and DOCX_NO_TEXT when the package has no extractable text.
 */
export async function extractDocxBlocks(buffer: ArrayBuffer): Promise<DocxBlock[]> {
  const view = new DataView(buffer);
  const entries = readZipEntries(view).filter(entry =>
    entry.name === DOCUMENT_ENTRY || (entry.name.startsWith('word/document') && entry.name.endsWith('.xml')),
  );
  if (entries.length === 0) throw new Error('DOCX_INVALID');
  const blocks: DocxBlock[] = [];
  for (const entry of entries) {
    const raw = readEntryBytes(view, entry);
    const bytes = entry.method === 0 ? raw : entry.method === 8 ? await inflateRaw(raw) : null;
    if (!bytes) throw new Error('DOCX_INVALID');
    blocks.push(...xmlToBlocks(new TextDecoder('utf-8').decode(bytes)));
  }
  if (!blocks.some(block => block.kind === 'table' || block.text.trim())) throw new Error('DOCX_NO_TEXT');
  return blocks;
}

/**
 * Paragraph-only view of the same document: table rows become tab-separated lines.
 * Kept for callers that only need text (search, copy), never for layout.
 */
export async function extractDocxParagraphs(buffer: ArrayBuffer): Promise<string[]> {
  const blocks = await extractDocxBlocks(buffer);
  return blocks.flatMap(block => (block.kind === 'paragraph' ? [block.text] : block.rows.map(row => row.join('\t'))));
}
