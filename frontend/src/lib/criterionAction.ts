import type { CriterionResult, HrCriterionReview } from '@/types';

/**
 * What a reviewer should do next about one criterion, decided from data that
 * actually exists — never from a guess and never from a second LLM call.
 *
 * The point is to stop making HR assemble the answer from three chips. Before
 * this, each card said "Đáp ứng · Bắt buộc · AI đối chiếu 64%" plus a citation
 * state, and the reviewer had to work out for themselves whether that meant
 * "nothing to do", "check this against the CV", or "the CV simply does not
 * mention it". Three different jobs looking identical is how work gets skipped.
 *
 * Every branch below is reachable from `determineCriterionAction`'s inputs. When
 * the data fits no branch, the card says so plainly instead of inventing a task.
 */
export type CriterionActionCode =
  | 'CONFIRMED'
  | 'REVIEWED_AS_WRONG'
  | 'NEEDS_CHECK'
  | 'NOT_IN_CV'
  | 'MISMATCH_CHECK'
  | 'ENOUGH_EVIDENCE'
  | 'OPEN_CV';

export interface CriterionAction {
  code: CriterionActionCode;
  /** Vietnamese key; the caller passes it through `t()`. */
  text: string;
  /** 0..2 — how much this asks of the reviewer. Drives colour, nothing else. */
  weight: 'none' | 'look' | 'act';
}

function latestReview(reviews?: HrCriterionReview[]) {
  return reviews && reviews.length ? reviews[0] : null;
}

export function determineCriterionAction(
  result: Pick<CriterionResult, 'outcome' | 'requires_verification' | 'evidence' | 'page_number' | 'verbatim_quote'> & {
    hr_reviews?: HrCriterionReview[];
  },
): CriterionAction {
  const review = latestReview(result.hr_reviews);
  const citation = result.evidence?.[0];
  const state = citation?.verification_status;
  const page = citation?.page_number ?? result.page_number;
  const hasQuote = Boolean(result.verbatim_quote || citation?.verbatim_quote);
  const hasPage = typeof page === 'number' && page > 0;

  // A recorded decision outranks everything: it is the newest piece of truth and
  // re-deriving a task from the engine's verdict would ask HR to redo work.
  if (review) {
    return review.decision === 'CONFIRMED'
      ? { code: 'CONFIRMED', text: 'Đã kiểm và xác nhận — không cần làm gì thêm', weight: 'none' }
      : { code: 'REVIEWED_AS_WRONG', text: 'Bạn đã đánh dấu trích dẫn này sai — cần xem lại cách đánh giá', weight: 'act' };
  }

  // The engine searched the CV and did not find the quote. That is a stronger
  // reason to look by hand than "nobody checked yet", so it comes first.
  if (state === 'FAILED') {
    return { code: 'MISMATCH_CHECK', text: 'Máy tìm không thấy trích dẫn trong CV — kiểm tra thủ công trước khi kết luận', weight: 'act' };
  }

  if (result.requires_verification) {
    if (!hasQuote) {
      return { code: 'NOT_IN_CV', text: 'CV không nêu tiêu chí này — cần hỏi thêm khi phỏng vấn', weight: 'look' };
    }
    if (hasPage) {
      return { code: 'NEEDS_CHECK', text: 'Đối chiếu trích dẫn với CV trang {0}, rồi xác nhận', weight: 'act' };
    }
    return { code: 'NEEDS_CHECK', text: 'Đối chiếu trích dẫn với CV rồi xác nhận', weight: 'act' };
  }

  if (state === 'VERIFIED' || state === 'MANUAL_FIX') {
    return { code: 'ENOUGH_EVIDENCE', text: 'Đã đủ bằng chứng và máy đã xác minh — không cần làm gì', weight: 'none' };
  }

  if (hasQuote && hasPage) {
    return { code: 'OPEN_CV', text: 'Xem trích dẫn trong CV nếu cần — máy chưa đối chiếu tiêu chí này', weight: 'look' };
  }

  // Nothing conclusive and nothing flagged: say that, do not invent a task.
  return { code: 'OPEN_CV', text: 'Chưa có bằng chứng rõ ràng — xem CV để kết luận', weight: 'look' };
}
