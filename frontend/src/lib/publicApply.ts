// Public application portal helpers. This module deliberately does not use the
// authenticated axios client: candidates have no account, and a signed-in HR
// user's token must never be attached to a candidate submission.

export const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.jpg', '.jpeg', '.png'];
// Mirrors the backend default MAX_FILE_SIZE_BYTES; the server remains the authority.
export const MAX_FILE_BYTES = 10_000_000;
// Version of the consent wording rendered by ApplyPage. Deploy wording and
// backend PUBLIC_INTAKE_NOTICE_VERSION together; never infer it from the server.
export const CONSENT_NOTICE_VERSION = 'v4';

export type PublicPosition = { code: string; title: string; unit?: string | null; location?: string | null; employment_type?: string | null };

export type ApplyFailure = 'RATE_LIMIT' | 'UNAVAILABLE' | 'POSITION_CLOSED' | 'CONSENT' | 'NOTICE_CHANGED' | 'FILE' | 'NETWORK';

export function validateCv(file: File | null): 'MISSING' | 'TYPE' | 'SIZE' | null {
  if (!file) return 'MISSING';
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext))) return 'TYPE';
  if (file.size === 0 || file.size > MAX_FILE_BYTES) return 'SIZE';
  return null;
}

export function failureFromStatus(status: number): ApplyFailure {
  if (status === 429) return 'RATE_LIMIT';
  if (status === 503) return 'UNAVAILABLE';
  if (status === 404) return 'POSITION_CLOSED';
  if (status === 409) return 'NOTICE_CHANGED';
  if (status === 413 || status === 400) return 'FILE';
  return 'NETWORK';
}

export async function fetchPublicPositions(): Promise<PublicPosition[]> {
  const response = await fetch('/v1/public/positions', { cache: 'no-store' });
  if (!response.ok) throw new Error(String(response.status));
  return (await response.json()).positions as PublicPosition[];
}

export async function submitApplication(code: string, file: File, consentProcessing: boolean, honeypot: string): Promise<{ ok: true; withdrawalToken?: string } | { ok: false; failure: ApplyFailure }> {
  if (!consentProcessing) return { ok: false, failure: 'CONSENT' };
  const body = new FormData();
  body.append('file', file);
  body.append('consent_processing', 'true');
  body.append('notice_version', CONSENT_NOTICE_VERSION);
  body.append('website', honeypot);
  try {
    const response = await fetch(`/v1/public/positions/${encodeURIComponent(code)}/apply`, { method: 'POST', body });
    if (response.ok) {
      const data = await response.json();
      if (data.status !== 'received' || !/^[0-9a-f]{64}$/.test(data.withdrawal_token ?? '')) {
        return { ok: false, failure: 'NETWORK' };
      }
      return { ok: true, withdrawalToken: data.withdrawal_token };
    }
    return { ok: false, failure: failureFromStatus(response.status) };
  } catch {
    return { ok: false, failure: 'NETWORK' };
  }
}

export async function withdrawTalentPool(token: string): Promise<boolean> {
  try {
    const response = await fetch('/v1/public/talent-pool/withdraw', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: token.trim().toLowerCase() }),
    });
    return response.ok;
  } catch {
    return false;
  }
}
