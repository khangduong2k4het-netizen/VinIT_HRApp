import type { ApplicationWithAssessment } from '@/types';

/**
 * One permission object for the application screen.
 *
 * Each field names an action the screen offers and mirrors the gate its endpoint
 * enforces, so a control is never shown to someone the API will answer with 403:
 *
 *  - `reviewEvidence`    POST /assessments/results/{id}/review (HR-notes capability)
 *  - `updateStatus`      PATCH /applications/{id}/status
 *  - `viewStatusHistory` GET  /applications/{id}/status-events
 *  - `reprocessCv`       POST /applications/{id}/reprocess
 *  - `editProfile`       PUT  /applications/{id}/profile
 *  - `manageHrNotes`     GET/POST /applications/{id}/private-notes
 *  - `viewCv`            GET  /applications/{id}/cv-file
 *  - `viewEvidence`      criteria evidence inside GET /applications/{id}
 */
export interface ApplicationCapabilities {
  viewCv: boolean;
  viewEvidence: boolean;
  updateStatus: boolean;
  reviewEvidence: boolean;
  manageHrNotes: boolean;
  editProfile: boolean;
  viewStatusHistory: boolean;
  reprocessCv: boolean;
}

type ServerCapabilities = {
  view_cv?: boolean;
  view_evidence?: boolean;
  update_status?: boolean;
  review_evidence?: boolean;
  manage_hr_notes?: boolean;
  edit_profile?: boolean;
  view_status_history?: boolean;
  reprocess_cv?: boolean;
};

/**
 * Read the server's `capabilities` object, falling back to the three flat flags
 * for payloads that predate it (and for the queue list, which only sets
 * cv/status). A fallback never grants more than the flat flag it stands for, and
 * a missing field is `false`: hiding a control is recoverable, a 403 is not.
 */
export function readApplicationCapabilities(application: ApplicationWithAssessment): ApplicationCapabilities {
  const raw: ServerCapabilities | undefined = application.capabilities;
  const fromServer = (key: keyof ServerCapabilities): boolean | undefined =>
    typeof raw?.[key] === 'boolean' ? Boolean(raw[key]) : undefined;
  const updateStatus = fromServer('update_status') ?? Boolean(application.can_update_status);
  const manageHrNotes = fromServer('manage_hr_notes') ?? Boolean(application.can_manage_hr_notes);
  return {
    viewCv: fromServer('view_cv') ?? Boolean(application.can_view_cv),
    viewEvidence: fromServer('view_evidence') ?? Boolean(application.can_view_assessment_evidence),
    updateStatus,
    // Recording a review is its own gate. It used to follow `can_update_status`,
    // so a status-only reviewer (for example a global ADMIN) saw the buttons and
    // got 403 from the review endpoint.
    reviewEvidence: fromServer('review_evidence') ?? manageHrNotes,
    manageHrNotes,
    editProfile: fromServer('edit_profile') ?? updateStatus,
    viewStatusHistory: fromServer('view_status_history') ?? updateStatus,
    reprocessCv: fromServer('reprocess_cv') ?? updateStatus,
  };
}
