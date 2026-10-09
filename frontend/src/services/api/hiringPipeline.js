// Hiring pipeline: screen -> L1 -> L2 -> offer -> onboarding -> BGV -> bench -> client.
// The backend derives each candidate's stage from facts; these calls supply the facts
// only people can give (screen decision, round verdicts, document checks, BGV, client date).
import { apiRequest } from "./client";

const get = async (path) => (await apiRequest(path, { method: "GET" })).data;
const post = async (path, body) =>
  (await apiRequest(path, { method: "POST", body: JSON.stringify(body || {}) })).data;
const put = async (path, body) => (await apiRequest(path, { method: "PUT", body: JSON.stringify(body || {}) })).data;

export const listPipelines = (stage) => get(`/hiring-pipeline${stage ? `?stage=${encodeURIComponent(stage)}` : ""}`);
export const getCandidatePipeline = (candidateId) => get(`/hiring-pipeline/candidate/${encodeURIComponent(candidateId)}`);
export const evaluatePipeline = (candidateId) =>
  post(`/hiring-pipeline/candidate/${encodeURIComponent(candidateId)}/evaluate`);
export const recordScreen = (candidateId, decision) =>
  post(`/hiring-pipeline/candidate/${encodeURIComponent(candidateId)}/screen`, { decision });
export const getOnboarding = (candidateId) =>
  get(`/hiring-pipeline/candidate/${encodeURIComponent(candidateId)}/onboarding`);
export const reviewDocument = (docId, decision) =>
  post(`/hiring-pipeline/preboarding-documents/${docId}/review`, { decision });

export const listVerdicts = (candidateId) => get(`/interviews/candidates/${encodeURIComponent(candidateId)}/verdicts`);
export const setRoundLevel = (panelId, level) => put(`/interviews/panels/${panelId}/level`, { level });
export const decideRound = (panelId, verdict, rationale) =>
  post(`/interviews/panels/${panelId}/verdict`, { verdict, rationale });

export const getCandidateBgv = (candidateId) => get(`/bgv/candidate/${encodeURIComponent(candidateId)}`);
export const startBgv = (bgvId, vendorName, vendorReference) =>
  post(`/bgv/${bgvId}/start`, { vendor_name: vendorName, vendor_reference: vendorReference });
export const recordBgvVerdict = (bgvId, verdict, notes) => post(`/bgv/${bgvId}/verdict`, { verdict, notes });
export const waiveBgv = (bgvId, reason) => post(`/bgv/${bgvId}/waive`, { reason });

export const listClientOnboardings = (status) =>
  get(`/client-onboarding${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const confirmClientStart = (onboardingId, confirmedStartDate) =>
  post(`/client-onboarding/${onboardingId}/confirm-start`, { confirmed_start_date: confirmedStartDate });
