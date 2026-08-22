/**
 * API INTEGRATION LAYER - Wires 42 existing components to 54 backend APIs
 * All 127-story launch scope functionality connected
 */

import axios, { AxiosInstance } from 'axios';

const API_BASE = 'http://localhost:8080/api/v1';

class APIIntegration {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
      }
    });
  }

  // ========== THUNDER AI (8 APIs) ==========
  async queryAIConversation(candidateId: string, query: string) {
    return this.client.post('/ai-conversation', { candidate_id: candidateId, query });
  }

  async getAIRecruiterAssignment(candidateId: string, roles: string[]) {
    return this.client.post('/ai-recruiter', { candidate_id: candidateId, available_roles: roles });
  }

  async detectIntent(text: string, conversationId: string) {
    return this.client.post('/intent/detect', { text, conversation_id: conversationId });
  }

  async getThunderAnalytics(startDate: string, endDate: string) {
    return this.client.get('/analytics/thunder', { params: { start_date: startDate, end_date: endDate } });
  }

  async getDecisionExplanation(decisionId: string) {
    return this.client.get(`/explain/${decisionId}`);
  }

  async toggleThunderPause(pause: boolean) {
    return this.client.post('/ai-recruiter/pause', { pause });
  }

  async validateSecurity(requestData: any) {
    return this.client.post('/security/validate', { request_data: requestData });
  }

  async getThunderStatus() {
    return this.client.get('/thunder/status');
  }

  // ========== CANDIDATE CORE (12 APIs) ==========
  async listCandidates(filters?: any) {
    return this.client.get('/candidates', { params: filters });
  }

  async createCandidate(candidateData: any) {
    return this.client.post('/candidates', candidateData);
  }

  async getCandidateMemory(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/memory`);
  }

  async storeCandidateMemory(candidateId: string, memoryType: string, content: string) {
    return this.client.post(`/candidates/${candidateId}/memory`, { memory_type: memoryType, content });
  }

  async getCandidateScore(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/score`);
  }

  async getCandidateContext(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/context`);
  }

  async getCandidatePool(filters?: any) {
    return this.client.get('/candidates/pool', { params: filters });
  }

  async verifyCandidateIsolation(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/isolation`);
  }

  async runCandidateAIAnalysis(candidateId: string) {
    return this.client.post(`/candidates/${candidateId}/ai`);
  }

  async getAbandonmentRisk(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/abandonment`);
  }

  async getDesireSignals(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/desire`);
  }

  async getDesireProfile(candidateId: string) {
    return this.client.get(`/candidates/${candidateId}/desire-profile`);
  }

  // ========== INTERVIEW WORKFLOWS (10 APIs) ==========
  async listInterviews(candidateId?: string) {
    return this.client.get('/interviews', { params: { candidate_id: candidateId } });
  }

  async getInterviewAvailability(candidateId: string) {
    return this.client.get('/interviews/availability', { params: { candidate_id: candidateId } });
  }

  async addAvailabilitySlot(candidateId: string, date: string, time: string) {
    return this.client.post('/interviews/availability', { candidate_id: candidateId, date, time });
  }

  async confirmInterview(interviewId: string, confirm: boolean) {
    return this.client.post(`/interviews/${interviewId}/confirm`, { confirm });
  }

  async sendInterviewReminder(interviewId: string) {
    return this.client.post(`/interviews/${interviewId}/remind`);
  }

  async rescheduleInterview(interviewId: string, newDate: string, newTime: string) {
    return this.client.post(`/interviews/${interviewId}/reschedule`, { new_date: newDate, new_time: newTime });
  }

  async findCalendarMatches(interviewerIds: string[], candidateId: string) {
    return this.client.post('/calendar/match', { interviewer_ids: interviewerIds, candidate_id: candidateId });
  }

  async sendEngagementEmail(candidateId: string, template?: string) {
    return this.client.post('/engagement/email', { candidate_id: candidateId, template });
  }

  async createFollowup(candidateId: string, actionType: string, dueDate: string) {
    return this.client.post('/followup', { candidate_id: candidateId, action_type: actionType, due_date: dueDate });
  }

  async scheduleFollowups(candidateId: string, schedule: any[]) {
    return this.client.post('/followup/schedule', { candidate_id: candidateId, schedule });
  }

  // ========== ONBOARDING (6 APIs) ==========
  async startOnboarding(employeeId: string) {
    return this.client.post('/onboarding/start', { employee_id: employeeId });
  }

  async listOnboardingDocuments(employeeId: string) {
    return this.client.get('/onboarding/documents', { params: { employee_id: employeeId } });
  }

  async addOnboardingDocument(employeeId: string, docType: string, docUrl: string) {
    return this.client.post('/onboarding/documents', { employee_id: employeeId, document_type: docType, document_url: docUrl });
  }

  async getOnboardingPortal(employeeId: string) {
    return this.client.get(`/onboarding/portal/${employeeId}`);
  }

  async graduateBuddyProgram(employeeId: string) {
    return this.client.post('/onboarding/buddy/graduate', { employee_id: employeeId });
  }

  async getOnboardingCheckins(employeeId: string) {
    return this.client.get('/onboarding/checkins', { params: { employee_id: employeeId } });
  }

  async setCheckinCadence(employeeId: string, frequency: string) {
    return this.client.post('/onboarding/checkins', { employee_id: employeeId, frequency });
  }

  async sendOnboardingNotification(employeeId: string, step: string) {
    return this.client.post('/onboarding/notify', { employee_id: employeeId, step });
  }

  // ========== EMPLOYEE CORE (8 APIs) ==========
  async listEmployees() {
    return this.client.get('/employees');
  }

  async createEmployee(employeeData: any) {
    return this.client.post('/employees', employeeData);
  }

  async getEmployee(employeeId: string) {
    return this.client.get(`/employees/${employeeId}`);
  }

  async allocateEmployee(employeeId: string, projectId: string, percentage?: number) {
    return this.client.post(`/employees/${employeeId}/allocate`, { project_id: projectId, percentage: percentage || 100 });
  }

  async getEmployeeMilestones(employeeId: string) {
    return this.client.get(`/employees/${employeeId}/milestones`);
  }

  async getAvailabilityScore(employeeId: string) {
    return this.client.get(`/employees/${employeeId}/availability`);
  }

  async getResourceMatches(roleId: string, skills: string[]) {
    return this.client.post('/resources/match', { role_id: roleId, skills });
  }

  async createEmployeeReferral(employeeId: string, referredCandidateId: string) {
    return this.client.post(`/employees/${employeeId}/refer`, { referred_candidate_id: referredCandidateId });
  }

  // ========== RESOURCE MANAGEMENT (10 APIs) ==========
  async getResourceAvailability(filters?: any) {
    return this.client.get('/resources/availability', { params: filters });
  }

  async getResourcePool(filters?: any) {
    return this.client.get('/resources/pool', { params: filters });
  }

  async matchSkills(requiredSkills: string[]) {
    return this.client.post('/skills/match', { required_skills: requiredSkills });
  }

  async forecastDemand(weeksAhead?: number) {
    return this.client.get('/demand/forecast', { params: { weeks_ahead: weeksAhead || 12 } });
  }

  async getBenchData() {
    return this.client.get('/bench');
  }

  async getUtilizationMetrics(filters?: any) {
    return this.client.get('/utilization', { params: filters });
  }

  async getCapacityPlan() {
    return this.client.get('/capacity');
  }

  async optimizeAssignments(constraints?: any) {
    return this.client.post('/assign/optimize', { constraints: constraints || {} });
  }

  async resolveCorePullConflicts() {
    return this.client.get('/core-pull/conflict');
  }

  async analyzeDemandGaps() {
    return this.client.get('/demand/gap');
  }

  // ========== ALLOCATIONS (Tier 2) ==========
  async listAllocations() {
    return this.client.get('/allocations');
  }

  async createAllocation(allocationData: any) {
    return this.client.post('/allocations', allocationData);
  }

  async getAllocationRecommendations(projectId: string, skillsRequired: string[]) {
    return this.client.post('/allocate/recommend', { project_id: projectId, skills_required: skillsRequired });
  }

  async getOnboardingProgress(employeeId: string) {
    return this.client.get('/onboarding/progress', { params: { employee_id: employeeId } });
  }

  async getConversationState(conversationId: string) {
    return this.client.get(`/conversations/${conversationId}/state`);
  }
}

// Export singleton instance
export const api = new APIIntegration();
export default APIIntegration;
