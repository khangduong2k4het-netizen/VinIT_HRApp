/**
 * Read the text of a .docx in the browser, with no backend change and no
 * third-party document library.
 *
 * A .docx is a ZIP whose `word/document.xml` holds the visible text. Browsers can
 * already inflate raw DEFLATE (`DecompressionStream('deflate-raw')`), so we only
 * need to read the ZIP central directory ourselves, inflate that one entry, and
 * pull the `<w:t>` runs out of the XML. Rendering goes through React text nodes,
 * never `innerHTML`, so a CV cannot inject markup into the app.
 *
 * Deliberately limited: this is a reading aid for screening, not a renderer of
 * layout — tables, columns and styling are flattened to paragraphs. The original
 * file stays one click away ("Tải CV gốc"). Anything this cannot read (encrypted
 * or legacy .doc renamed to .docx) throws, so the caller can say so instead of
 * showing an empty panel.
 */

const LOCAL_HEADER_SIG = 0x04034b50;
const CENTRAL_HEADER_SIG = 0x02014b50;
const END_OF_CENTRAL_DIR_SIG = 0x06054b50;

const WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const DOCUMENT_ENTRY = 'word/document.xml';

type ZipEntry = { name: string; method: number; compressedSize: number; localHeaderOffset: number };

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

function xmlToParagraphs(xml: string): string[] {
  const doc = new DOMParser().parseFromString(xml, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length > 0) throw new Error('DOCX_INVALID');
  const paragraphs: string[] = [];
  for (const paragraph of Array.from(doc.getElementsByTagNameNS(WORD_NS, 'p'))) {
    const text = paragraphText(paragraph);
    // A blank paragraph is a visual gap; keep one, drop the runs of them that
    // Word files carry after tables.
    if (!text.trim() && (paragraphs.length === 0 || paragraphs[paragraphs.length - 1] === '')) continue;
    paragraphs.push(text);
  }
  while (paragraphs.length && paragraphs[paragraphs.length - 1] === '') paragraphs.pop();
  return paragraphs;
}

/**
 * Paragraphs of a .docx, in document order. Throws DOCX_INVALID for a file that
 * is not a readable ZIP, DOCX_UNSUPPORTED when the browser cannot inflate, and
 * DOCX_NO_TEXT when the package has no extractable text.
 */
export async function extractDocxParagraphs(buffer: ArrayBuffer): Promise<string[]> {
  const view = new DataView(buffer);
  const entries = readZipEntries(view).filter(entry =>
    entry.name === DOCUMENT_ENTRY || (entry.name.startsWith('word/document') && entry.name.endsWith('.xml')),
  );
  if (entries.length === 0) throw new Error('DOCX_INVALID');
  const paragraphs: string[] = [];
  for (const entry of entries) {
    const raw = readEntryBytes(view, entry);
    const bytes = entry.method === 0 ? raw : entry.method === 8 ? await inflateRaw(raw) : null;
    if (!bytes) throw new Error('DOCX_INVALID');
    paragraphs.push(...xmlToParagraphs(new TextDecoder('utf-8').decode(bytes)));
  }
  if (!paragraphs.some(line => line.trim())) throw new Error('DOCX_NO_TEXT');
  return paragraphs;
}
