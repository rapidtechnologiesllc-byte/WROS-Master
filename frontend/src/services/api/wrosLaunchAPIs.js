/**
 * WROS LAUNCH APIs - All 54 Critical Endpoints
 * Integrated with existing client.js pattern
 * Tier 1: Thunder AI (8) + Candidate Core (12)
 * Tier 2: Interview (10) + Onboarding (6)
 * Tier 3: Employee (8) + Resource (10)
 */

import { apiRequest } from "./client";

// ========== THUNDER AI (8 APIs) ==========
export const queryAIConversation = async (candidateId, query, context = {}) => {
  const { data } = await apiRequest("/api/v1/ai-conversation", {
    method: "POST",
    body: { candidate_id: candidateId, query, context }
  });
  return data;
};

export const getAIRecruiterAssignment = async (candidateId, availableRoles = []) => {
  const { data } = await apiRequest("/api/v1/ai-recruiter", {
    method: "POST",
    body: { candidate_id: candidateId, available_roles: availableRoles }
  });
  return data;
};

export const detectIntent = async (text, conversationId) => {
  const { data } = await apiRequest("/api/v1/intent/detect", {
    method: "POST",
    body: { text, conversation_id: conversationId }
  });
  return data;
};

export const getThunderAnalytics = async (startDate, endDate) => {
  const { data } = await apiRequest("/api/v1/analytics/thunder", {
    method: "GET",
    params: { start_date: startDate, end_date: endDate }
  });
  return data;
};

export const getDecisionExplanation = async (decisionId) => {
  const { data } = await apiRequest(`/api/v1/explain/${decisionId}`, {
    method: "GET"
  });
  return data;
};

export const toggleThunderPause = async (pause) => {
  const { data } = await apiRequest("/api/v1/ai-recruiter/pause", {
    method: "POST",
    body: { pause }
  });
  return data;
};

export const validateSecurity = async (requestData) => {
  const { data } = await apiRequest("/api/v1/security/validate", {
    method: "POST",
    body: { request_data: requestData }
  });
  return data;
};

export const getThunderStatus = async () => {
  const { data } = await apiRequest("/api/v1/thunder/status", {
    method: "GET"
  });
  return data;
};

// ========== CANDIDATE CORE (12 APIs) ==========
export const listCandidates = async (filters = {}) => {
  const { data } = await apiRequest("/api/v1/candidates", {
    method: "GET",
    params: filters
  });
  return data;
};

export const createCandidate = async (candidateData) => {
  const { data } = await apiRequest("/api/v1/candidates", {
    method: "POST",
    body: candidateData
  });
  return data;
};

export const getCandidateMemory = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/memory`, {
    method: "GET",
    allow404: true
  });
  return data;
};

export const storeCandidateMemory = async (candidateId, memoryType, content) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/memory`, {
    method: "POST",
    body: { memory_type: memoryType, content }
  });
  return data;
};

export const getCandidateScore = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/score`, {
    method: "GET"
  });
  return data;
};

export const getCandidateContext = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/context`, {
    method: "GET"
  });
  return data;
};

export const getCandidatePool = async (filters = {}) => {
  const { data } = await apiRequest("/api/v1/candidates/pool", {
    method: "GET",
    params: filters
  });
  return data;
};

export const verifyCandidateIsolation = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/isolation`, {
    method: "GET"
  });
  return data;
};

export const runCandidateAIAnalysis = async (candidateId, analysisType = "full") => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/ai`, {
    method: "POST",
    body: { analysis_type: analysisType }
  });
  return data;
};

export const getAbandonmentRisk = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/abandonment`, {
    method: "GET"
  });
  return data;
};

export const getDesireSignals = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/desire`, {
    method: "GET"
  });
  return data;
};

export const getDesireProfile = async (candidateId) => {
  const { data } = await apiRequest(`/api/v1/candidates/${candidateId}/desire-profile`, {
    method: "GET"
  });
  return data;
};

// ========== INTERVIEW WORKFLOWS (10 APIs) ==========
export const listInterviews = async (candidateId = null) => {
  const { data } = await apiRequest("/api/v1/interviews", {
    method: "GET",
    params: { ...(candidateId && { candidate_id: candidateId }) }
  });
  return data;
};

export const getInterviewAvailability = async (candidateId) => {
  const { data } = await apiRequest("/api/v1/interviews/availability", {
    method: "GET",
    params: { candidate_id: candidateId }
  });
  return data;
};

export const addAvailabilitySlot = async (candidateId, date, time) => {
  const { data } = await apiRequest("/api/v1/interviews/availability", {
    method: "POST",
    body: { candidate_id: candidateId, date, time }
  });
  return data;
};

export const confirmInterview = async (interviewId, confirm = true) => {
  const { data } = await apiRequest(`/api/v1/interviews/${interviewId}/confirm`, {
    method: "POST",
    body: { confirm }
  });
  return data;
};

export const sendInterviewReminder = async (interviewId) => {
  const { data } = await apiRequest(`/api/v1/interviews/${interviewId}/remind`, {
    method: "POST"
  });
  return data;
};

export const rescheduleInterview = async (interviewId, newDate, newTime) => {
  const { data } = await apiRequest(`/api/v1/interviews/${interviewId}/reschedule`, {
    method: "POST",
    body: { new_date: newDate, new_time: newTime }
  });
  return data;
};

export const findCalendarMatches = async (interviewerIds, candidateId) => {
  const { data } = await apiRequest("/api/v1/calendar/match", {
    method: "POST",
    body: { interviewer_ids: interviewerIds, candidate_id: candidateId }
  });
  return data;
};

export const sendEngagementEmail = async (candidateId, template = "default") => {
  const { data } = await apiRequest("/api/v1/engagement/email", {
    method: "POST",
    body: { candidate_id: candidateId, template }
  });
  return data;
};

export const createFollowup = async (candidateId, actionType, dueDate) => {
  const { data } = await apiRequest("/api/v1/followup", {
    method: "POST",
    body: { candidate_id: candidateId, action_type: actionType, due_date: dueDate }
  });
  return data;
};

export const scheduleFollowups = async (candidateId, schedule = []) => {
  const { data } = await apiRequest("/api/v1/followup/schedule", {
    method: "POST",
    body: { candidate_id: candidateId, schedule }
  });
  return data;
};

// ========== ONBOARDING (6 APIs) ==========
export const startOnboarding = async (employeeId) => {
  const { data } = await apiRequest("/api/v1/onboarding/start", {
    method: "POST",
    body: { employee_id: employeeId }
  });
  return data;
};

export const listOnboardingDocuments = async (employeeId) => {
  const { data } = await apiRequest("/api/v1/onboarding/documents", {
    method: "GET",
    params: { employee_id: employeeId }
  });
  return data;
};

export const addOnboardingDocument = async (employeeId, docType, docUrl) => {
  const { data } = await apiRequest("/api/v1/onboarding/documents", {
    method: "POST",
    body: { employee_id: employeeId, document_type: docType, document_url: docUrl }
  });
  return data;
};

export const getOnboardingPortal = async (employeeId) => {
  const { data } = await apiRequest(`/api/v1/onboarding/portal/${employeeId}`, {
    method: "GET"
  });
  return data;
};

export const graduateBuddyProgram = async (employeeId) => {
  const { data } = await apiRequest("/api/v1/onboarding/buddy/graduate", {
    method: "POST",
    body: { employee_id: employeeId }
  });
  return data;
};

export const getOnboardingCheckins = async (employeeId) => {
  const { data } = await apiRequest("/api/v1/onboarding/checkins", {
    method: "GET",
    params: { employee_id: employeeId }
  });
  return data;
};

// ========== EMPLOYEE CORE (8 APIs) ==========
export const listEmployees = async () => {
  const { data } = await apiRequest("/api/v1/employees", {
    method: "GET"
  });
  return data;
};

export const getEmployeeByID = async (employeeId) => {
  const { data } = await apiRequest(`/api/v1/employees/${employeeId}`, {
    method: "GET"
  });
  return data;
};

export const allocateEmployee = async (employeeId, projectId, percentage = 100) => {
  const { data } = await apiRequest(`/api/v1/employees/${employeeId}/allocate`, {
    method: "POST",
    body: { project_id: projectId, percentage }
  });
  return data;
};

export const getEmployeeMilestones = async (employeeId) => {
  const { data } = await apiRequest(`/api/v1/employees/${employeeId}/milestones`, {
    method: "GET"
  });
  return data;
};

export const getAvailabilityScore = async (employeeId) => {
  const { data } = await apiRequest(`/api/v1/employees/${employeeId}/availability`, {
    method: "GET"
  });
  return data;
};

export const getResourceMatches = async (roleId, skills = []) => {
  const { data } = await apiRequest("/api/v1/resources/match", {
    method: "POST",
    body: { role_id: roleId, skills }
  });
  return data;
};

export const createEmployeeReferral = async (employeeId, referredCandidateId) => {
  const { data } = await apiRequest(`/api/v1/employees/${employeeId}/refer`, {
    method: "POST",
    body: { referred_candidate_id: referredCandidateId }
  });
  return data;
};

// ========== RESOURCE MANAGEMENT (10 APIs) ==========
export const getResourceAvailability = async (filters = {}) => {
  const { data } = await apiRequest("/api/v1/resources/availability", {
    method: "GET",
    params: filters
  });
  return data;
};

export const getResourcePool = async (filters = {}) => {
  const { data } = await apiRequest("/api/v1/resources/pool", {
    method: "GET",
    params: filters
  });
  return data;
};

export const matchSkills = async (requiredSkills = []) => {
  const { data } = await apiRequest("/api/v1/skills/match", {
    method: "POST",
    body: { required_skills: requiredSkills }
  });
  return data;
};

export const forecastDemand = async (weeksAhead = 12) => {
  const { data } = await apiRequest("/api/v1/demand/forecast", {
    method: "GET",
    params: { weeks_ahead: weeksAhead }
  });
  return data;
};

export const getBenchData = async () => {
  const { data } = await apiRequest("/api/v1/bench", {
    method: "GET"
  });
  return data;
};

export const getUtilizationMetrics = async (filters = {}) => {
  const { data } = await apiRequest("/api/v1/utilization", {
    method: "GET",
    params: filters
  });
  return data;
};

export const getCapacityPlan = async () => {
  const { data } = await apiRequest("/api/v1/capacity", {
    method: "GET"
  });
  return data;
};

export const optimizeAssignments = async (constraints = {}) => {
  const { data } = await apiRequest("/api/v1/assign/optimize", {
    method: "POST",
    body: { constraints }
  });
  return data;
};

export const resolveCorePullConflicts = async () => {
  const { data } = await apiRequest("/api/v1/core-pull/conflict", {
    method: "GET"
  });
  return data;
};

export const analyzeDemandGaps = async () => {
  const { data } = await apiRequest("/api/v1/demand/gap", {
    method: "GET"
  });
  return data;
};

// ========== ADDITIONAL TIER 2 & 3 ==========
export const listAllocations = async () => {
  const { data } = await apiRequest("/api/v1/allocations", {
    method: "GET"
  });
  return data;
};

export const getAllocationRecommendations = async (projectId, skillsRequired = []) => {
  const { data } = await apiRequest("/api/v1/allocate/recommend", {
    method: "POST",
    body: { project_id: projectId, skills_required: skillsRequired }
  });
  return data;
};

export const getOnboardingProgress = async (employeeId) => {
  const { data } = await apiRequest("/api/v1/onboarding/progress", {
    method: "GET",
    params: { employee_id: employeeId }
  });
  return data;
};

export const getConversationState = async (conversationId) => {
  const { data } = await apiRequest(`/api/v1/conversations/${conversationId}/state`, {
    method: "GET"
  });
  return data;
};
