// Public application portal helpers. This module deliberately does not use the
// authenticated axios client: candidates have no account, and a signed-in HR
// user's token must never be attached to a candidate submission.

export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.jpg', '.jpeg', '.png'];
// Mirrors the backend default MAX_FILE_SIZE_BYTES; the server remains the authority.
export const MAX_FILE_BYTES = 10_000_000;

export type PublicPosition = { code: string; title: string; unit?: string | null; location?: string | null; employment_type?: string | null };

export type ApplyFailure = 'RATE_LIMIT' | 'UNAVAILABLE' | 'POSITION_CLOSED' | 'CONSENT' | 'FILE' | 'NETWORK';

export function validateCv(file: File | null): 'MISSING' | 'TYPE' | 'SIZE' | null {
  if (!file) return 'MISSING';
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext))) return 'TYPE';
  if (file.size > MAX_FILE_BYTES) return 'SIZE';
  return null;
}

export function failureFromStatus(status: number): ApplyFailure {
  if (status === 429) return 'RATE_LIMIT';
  if (status === 503) return 'UNAVAILABLE';
  if (status === 404) return 'POSITION_CLOSED';
  if (status === 413 || status === 400) return 'FILE';
  return 'NETWORK';
}

export async function fetchPublicPositions(): Promise<PublicPosition[]> {
  const response = await fetch('/v1/public/positions', { cache: 'no-store' });
  if (!response.ok) throw new Error(String(response.status));
  return (await response.json()).positions as PublicPosition[];
}

export async function submitApplication(code: string, file: File, consentTalentPool: boolean, honeypot: string): Promise<{ ok: true } | { ok: false; failure: ApplyFailure }> {
  const body = new FormData();
  body.append('file', file);
  // Reaching this function means the required box was ticked (the form enforces it).
  body.append('consent_processing', 'true');
  body.append('consent_talent_pool', consentTalentPool ? 'true' : 'false');
  body.append('website', honeypot);
  try {
    const response = await fetch(`/v1/public/positions/${encodeURIComponent(code)}/apply`, { method: 'POST', body });
    if (response.ok) return { ok: true };
    return { ok: false, failure: failureFromStatus(response.status) };
  } catch {
    return { ok: false, failure: 'NETWORK' };
  }
}
