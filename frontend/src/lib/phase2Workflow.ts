/** Presentation helpers only; the backend remains the authority for validation. */
export type CompletionCriterion = { rating: number | null; insufficient_evidence: boolean };
export function scorecardIsComplete(recommendation: string | null, criteria: CompletionCriterion[]): boolean {
  return !!recommendation && criteria.length > 0 && criteria.every(item =>
    item.insufficient_evidence ? item.rating === null : item.rating !== null && Number.isInteger(item.rating) && item.rating >= 1 && item.rating <= 5);
}
export function rubricKeywords(value: string): string[] {
  return value.split(',').map(item => item.trim()).filter(Boolean);
}
export function optionalRequirementSpec(value: string): unknown {
  return value.trim() ? JSON.parse(value) : null;
}
