'use client';

import axios, { AxiosInstance } from 'axios';
import { localizeServerMessage } from '@/i18n/serverMessages';
import type { TemplateItemInput, ScorecardUpdateInput } from '@/types';

// The browser always uses the same origin. Next.js proxies /v1 to the backend,
// which also works when the UI is viewed through a remote preview host.
const apiClient: AxiosInstance = axios.create({
  baseURL: '/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to attach auth token
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('hra_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Add response interceptor to handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.data?.detail) error.response.data.detail = localizeServerMessage(error.response.data.detail);
    if (error.response?.status === 401 && typeof window !== 'undefined' && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('hra_access_token');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export default apiClient;

export const qualityApi = {
  list: (params: { position_id?: string; status?: string; offset?: number }) => apiClient.get('/quality/inspections', { params }),
  sample: (positionId: string) => apiClient.post(`/quality/positions/${positionId}/sample`),
  detail: (id: string) => apiClient.get(`/quality/inspections/${id}`),
  source: (id: string) => apiClient.get(`/quality/inspections/${id}/source`, { responseType: 'blob' }),
  text: (id: string) => apiClient.get(`/quality/inspections/${id}/text`),
  feedback: (id: string) => apiClient.get(`/quality/inspections/${id}/feedback`),
  claim: (id: string, revision: number) => apiClient.post(`/quality/inspections/${id}/claim`, { expected_revision: revision }),
  submit: (id: string, data: unknown) => apiClient.post(`/quality/inspections/${id}/submit`, data),
};

export const crossDuplicatesApi = {
  list: (id: string) => apiClient.get(`/cross-duplicates/applications/${id}`),
  scan: (id: string) => apiClient.post(`/cross-duplicates/applications/${id}/scan`),
  review: (id: string, decision: 'CONFIRMED' | 'DISMISSED') => apiClient.post(`/cross-duplicates/signals/${id}/review`, { decision }),
};

// F2.09: side-by-side comparison and custom export (never contains email/phone).
export const candidateReportsApi = {
  compare: (positionId: string, applicationIds: string[]) =>
    apiClient.get(`/candidate-reports/positions/${positionId}/comparison`, {
      params: { application_ids: applicationIds },
      paramsSerializer: { indexes: null },
    }),
  export: (positionId: string, data: {
    format: 'xlsx' | 'pdf'; columns: string[]; application_ids?: string[]; language: 'vi' | 'en';
  }) => apiClient.post(`/candidate-reports/positions/${positionId}/export`, data, { responseType: 'blob' }),
};

// API Functions
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/auth/login', { email, password }),
  me: () => apiClient.get('/auth/me'),
  bootstrapStatus: () => apiClient.get('/auth/bootstrap-status'),
  bootstrap: (data: { email: string; display_name: string; password: string; setup_token: string }) =>
    apiClient.post('/auth/bootstrap', data),
  changePassword: (current_password: string, new_password: string) =>
    apiClient.post('/auth/change-password', { current_password, new_password }),
};

export const positionsApi = {
  list: (status?: string, q?: string) =>
    apiClient.get('/positions', { params: { status, q: q || undefined } }),
  listAll: async () => {
    const all: any[] = [];
    for (let page = 1; ; page += 1) {
      const response = await apiClient.get('/positions', { params: { page, page_size: 100 } });
      all.push(...response.data);
      if (response.data.length < 100) return all;
    }
  },
  create: (data: any) => apiClient.post('/positions', data),
  getById: (id: string) => apiClient.get(`/positions/${id}`),
  getWorkspace: (id: string) => apiClient.get(`/positions/${id}/workspace`),
  update: (id: string, data: any) => apiClient.patch(`/positions/${id}`, data),
  getStatusEvents: (id: string) => apiClient.get(`/positions/${id}/status-events`),
  getJdVersions: (id: string) => apiClient.get(`/positions/${id}/jd-versions`),
  getJdVersion: (id: string, jdVersionId: string) => apiClient.get(`/positions/${id}/jd-versions/${jdVersionId}`),
  createJdVersion: (id: string, data: { content_text: string; language_code: string; expected_jd_version_id: string }) => apiClient.post(`/positions/${id}/jd-versions`, data),
};

export const departmentsApi = {
  list: (includeInactive = false) => apiClient.get('/departments', { params: { include_inactive: includeInactive } }),
  create: (data: { name: string; code_format: string; is_active: boolean }) => apiClient.post('/departments', data),
  update: (id: string, data: { name?: string; code_format?: string; is_active?: boolean }) => apiClient.patch(`/departments/${id}`, data),
  delete: (id: string) => apiClient.delete(`/departments/${id}`),
};

export const criteriaApi = {
  listVersions: (positionId: string) =>
    apiClient.get(`/criteria/position/${positionId}/versions`),
  getById: (id: string) => apiClient.get(`/criteria/${id}`),
  generateDraft: (positionId: string) =>
    apiClient.post(`/criteria/generate/${positionId}`),
  approve: (id: string, action: 'APPROVE' | 'DIRECT_APPROVE' | 'REJECT' | 'REQUEST_CHANGES', comment?: string) =>
    apiClient.post(`/criteria/${id}/approve`, { action, comment }),
  getApprovalEvents: (id: string) => apiClient.get(`/criteria/${id}/approval-events`),
  createItem: (versionId: string, data: { name: string; description: string; category: 'MUST_HAVE' | 'NICE_TO_HAVE'; weight_in_group: number; expected_evidence_keywords: string[]; requirement_spec?: import('@/types').RequirementSpec | null }) =>
    apiClient.post(`/criteria/${versionId}/items`, data),
  updateItem: (versionId: string, itemId: string, data: { name: string; description: string; category: 'MUST_HAVE' | 'NICE_TO_HAVE'; weight_in_group: number; expected_evidence_keywords: string[]; requirement_spec?: import('@/types').RequirementSpec | null }) =>
    apiClient.patch(`/criteria/${versionId}/items/${itemId}`, data),
  deleteItem: (versionId: string, itemId: string) =>
    apiClient.delete(`/criteria/${versionId}/items/${itemId}`),
  updateItemWeights: (versionId: string, items: { criterion_id: string; weight_in_group: number }[]) =>
    apiClient.patch(`/criteria/${versionId}/items/weights`, { items }),
  updateWeights: (versionId: string, mandatory: number, nice: number) =>
    apiClient.patch(`/criteria/${versionId}/weights`, { mandatory_weight_total: mandatory, nice_to_have_weight_total: nice }),
  getApproved: (positionId: string) =>
    apiClient.get(`/criteria/position/${positionId}/approved`),
  // F1.02: copy an approved/rejected rubric into a new HR draft.
  createNewVersion: (versionId: string) =>
    apiClient.post(`/criteria/${versionId}/new-version`),
  // F2.01: apply a published rubric template as a criteria draft.
  getTemplateMatches: (positionId: string) =>
    apiClient.get(`/criteria/position/${positionId}/template-matches`),
  applyTemplate: (positionId: string, templateVersionId: string) =>
    apiClient.post(`/criteria/position/${positionId}/apply-template`, { template_version_id: templateVersionId }),
};

// F2.01 — Rubric library
export const rubricApi = {
  listFamilies: (includeInactive = false) =>
    apiClient.get('/rubric-library/families', { params: { include_inactive: includeInactive || undefined } }),
  createFamily: (data: { code: string; name: string; description?: string | null; display_order?: number }) =>
    apiClient.post('/rubric-library/families', data),
  updateFamily: (id: string, data: { name?: string; description?: string | null; status?: 'ACTIVE' | 'INACTIVE'; display_order?: number }) =>
    apiClient.patch(`/rubric-library/families/${id}`, data),
  listTemplates: (params: { job_family_id?: string; level_band?: string; status?: 'PUBLISHED' | 'DRAFT_ONLY' | 'ALL'; q?: string }) =>
    apiClient.get('/rubric-library/templates', { params }),
  createTemplate: (data: { job_family_id: string; title: string; level_band?: string | null; change_note?: string | null }) =>
    apiClient.post('/rubric-library/templates', data),
  getTemplate: (id: string) => apiClient.get(`/rubric-library/templates/${id}`),
  createVersion: (templateId: string, data: { source_version_id?: string; change_note?: string | null }) =>
    apiClient.post(`/rubric-library/templates/${templateId}/versions`, data),
  getVersion: (id: string) => apiClient.get(`/rubric-library/template-versions/${id}`),
  updateVersion: (id: string, data: { mandatory_weight_total?: number; nice_to_have_weight_total?: number; change_note?: string | null }) =>
    apiClient.patch(`/rubric-library/template-versions/${id}`, data),
  addItem: (versionId: string, data: TemplateItemInput) =>
    apiClient.post(`/rubric-library/template-versions/${versionId}/items`, data),
  updateItem: (itemId: string, data: Partial<TemplateItemInput>) =>
    apiClient.patch(`/rubric-library/template-items/${itemId}`, data),
  deleteItem: (itemId: string) => apiClient.delete(`/rubric-library/template-items/${itemId}`),
  publish: (versionId: string, comment?: string) =>
    apiClient.post(`/rubric-library/template-versions/${versionId}/publish`, { comment: comment || null }),
  archive: (versionId: string, comment?: string) =>
    apiClient.post(`/rubric-library/template-versions/${versionId}/archive`, { comment: comment || null }),
};

// F2.02 — Structured scorecards
export const scorecardApi = {
  mine: (status?: 'NOT_STARTED' | 'IN_PROGRESS' | 'SUBMITTED' | 'OVERDUE' | 'OPEN') =>
    apiClient.get('/shortlist/my-scorecards', { params: { status } }),
  get: (id: string) => apiClient.get(`/shortlist/scorecards/${id}`),
  save: (id: string, data: ScorecardUpdateInput) => apiClient.patch(`/shortlist/scorecards/${id}`, data),
  submit: (id: string) => apiClient.post(`/shortlist/scorecards/${id}/submit`),
  reopen: (id: string, reason: string) => apiClient.post(`/shortlist/scorecards/${id}/reopen`, { reason }),
  summary: (shareId: string) => apiClient.get(`/shortlist/${shareId}/scorecard-summary`),
};

export const applicationsApi = {
  uploadBatch: (positionId: string, files: File[], onProgress?: (percent: number) => void) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return apiClient.post(`/applications/upload-batch/${positionId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      },
    });
  },
  list: (positionId: string, params?: any) =>
    apiClient.get('/applications', { params: { position_id: positionId, ...params } }),
  listAll: async (positionId: string) => {
    const all: any[] = [];
    const pageSize = 100;
    for (let page = 1; ; page += 1) {
      const response = await apiClient.get('/applications', {
        params: { position_id: positionId, page, page_size: pageSize },
      });
      all.push(...response.data);
      if (response.data.length < pageSize) return all;
    }
  },
  getById: (id: string) => apiClient.get(`/applications/${id}`),
  getProfile: (id: string) => apiClient.get(`/applications/${id}/profile`),
  updateProfile: (id: string, data: any) => apiClient.put(`/applications/${id}/profile`, data),
  getPrivateNotes: (id: string) => apiClient.get(`/applications/${id}/private-notes`),
  addPrivateNote: (id: string, content: string) => apiClient.post(`/applications/${id}/private-notes`, { content }),
  getStatusEvents: (id: string) => apiClient.get(`/applications/${id}/status-events`),
  reprocess: (id: string) => apiClient.post(`/applications/${id}/reprocess`),
  updateStatus: (id: string, newStatus: string, reason?: string, note?: string, overrideReasonCode?: string) =>
    apiClient.patch(`/applications/${id}/status`, { new_status: newStatus, reason, note, override_reason_code: overrideReasonCode }),
  // F2.03: does this decision contradict the AI conclusion (and so need a reason)?
  checkOverride: (id: string, newStatus: string) =>
    apiClient.get(`/applications/${id}/override-check`, { params: { new_status: newStatus } }),
  getCvUrl: (id: string) => apiClient.get(`/applications/${id}/cv-download-url`),
  getCvBlob: (id: string) => apiClient.get(`/applications/${id}/cv-file`, { responseType: 'blob' }),
};

export const operationsApi = {
  getStatus: (id: string) => apiClient.get(`/operations/${id}`),
  getActiveForPosition: (id: string) => apiClient.get(`/operations/position/${id}/active`),
};

export const assessmentsApi = {
  runForPosition: (positionId: string) =>
    apiClient.post(`/assessments/run/${positionId}`),
  getById: (id: string) => apiClient.get(`/assessments/${id}`),
  generateRanking: (positionId: string) =>
    apiClient.post(`/assessments/ranking/generate/${positionId}`),
  getLatestRanking: (positionId: string) =>
    apiClient.get(`/assessments/ranking/latest/${positionId}`),
};

export const usersApi = {
  list: (params?: { search?: string; position_id?: string; role?: 'HIRING_MANAGER' }) =>
    apiClient.get('/users', { params }),
};

export const shortlistApi = {
  create: (data: any) => apiClient.post('/shortlist/share', data),
  getSharedWithMe: () => apiClient.get('/shortlist/shared-with-me'),
  getDetail: (id: string) => apiClient.get(`/shortlist/${id}`),
  getPotentialRecipients: (positionId: string) =>
    apiClient.get(`/shortlist/potential-recipients/${positionId}`),
  getShortlistedApps: (positionId: string) =>
    apiClient.get(`/shortlist/shortlisted-applications/${positionId}`),
  addFeedback: (id: string, content: string, applicationId?: string) =>
    apiClient.post(`/shortlist/${id}/feedback`, { content, application_id: applicationId }),
  revoke: (id: string) => apiClient.post(`/shortlist/${id}/revoke`),
};

export const dashboardApi = {
  getSummary: () => apiClient.get('/dashboard/summary'),
  getWorkQueue: () => apiClient.get('/dashboard/work-queue'),
  getPosition: (id: string) => apiClient.get(`/dashboard/position/${id}`),
};

export const adminApi = {
  listUsers: (params: { search?: string; role?: string; account_status?: string; page?: number }) =>
    apiClient.get('/admin/users', { params }),
  createUser: (data: { email: string; display_name: string; password: string; roles: string[] }) =>
    apiClient.post('/admin/users', data),
  updateUser: (id: string, data: { display_name: string; account_status: string; roles: string[] }) =>
    apiClient.patch(`/admin/users/${id}`, data),
  resetUserPassword: (id: string, new_password: string) =>
    apiClient.post(`/admin/users/${id}/reset-password`, { new_password }),
  listAiConfigs: () => apiClient.get('/admin/ai/config'),
  testAiConnection: (data: any) => apiClient.post('/admin/ai/test-connection', data),
  createAiConfig: (data: any) => apiClient.post('/admin/ai/config', data),
  enableAiConfig: (id: string) => apiClient.post(`/admin/ai/config/${id}/enable`),
  getActiveAiConfig: () => apiClient.get('/admin/ai/active-config'),
  getWorkerHealth: () => apiClient.get('/admin/worker/health'),
  getAiOptions: () => apiClient.get('/admin/ai/options'),
};

// F1.10 / S-19 — retention queue and explicit, audited deletion.
// F2.07 — exception hold, reminders and a one-time code before purge.
export const retentionApi = {
  queue: (status?: 'PENDING' | 'SCHEDULED_FOR_DELETION' | 'ON_HOLD' | 'DELETED' | 'CANCELLED') =>
    apiClient.get('/retention/queue', { params: { status } }),
  generate: (positionId: string) => apiClient.post(`/retention/positions/${positionId}/cases/generate`),
  confirm: (caseId: string) => apiClient.post(`/retention/cases/${caseId}/confirm`, {}),
  cancel: (caseId: string) => apiClient.post(`/retention/cases/${caseId}/cancel`, {}),
  requestPurgeOtp: (caseId: string) => apiClient.post(`/retention/cases/${caseId}/purge-otp`),
  execute: (caseId: string, challengeId?: string, otp?: string) =>
    apiClient.post(`/retention/cases/${caseId}/execute`, challengeId ? { challenge_id: challengeId, otp } : {}),
  hold: (caseId: string, data: { reason_code: string; legal_approval_reference: string; hold_until?: string | null }) =>
    apiClient.post(`/retention/cases/${caseId}/hold`, data),
  releaseHold: (caseId: string) => apiClient.post(`/retention/cases/${caseId}/release-hold`),
  notifications: (unreadOnly = false) => apiClient.get('/retention/notifications', { params: { unread_only: unreadOnly } }),
  markNotificationRead: (id: string) => apiClient.post(`/retention/notifications/${id}/read`),
  runCycle: () => apiClient.post('/retention/cycle/run'),
};

// F1.10 / S-20 — audit trail (Admin only; metadata is never returned).
export const auditApi = {
  list: (params: { action_type?: string; actor_user_id?: string; position_id?: string; date_from?: string; date_to?: string; page?: number; page_size?: number }) =>
    apiClient.get('/admin/audit/events', { params }),
  verify: () => apiClient.get('/admin/audit/verify'),
};

// F2.03 — operational analytics (pilot report).
export const analyticsApi = {
  operations: (params: { date_from?: string; date_to?: string; position_id?: string; department_id?: string }) =>
    apiClient.get('/analytics/operations', { params }),
};
