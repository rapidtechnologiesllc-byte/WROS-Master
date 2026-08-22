/**
 * React Hook - useAPI
 * Provides all 54 backend API methods to components
 */

import { useState, useCallback } from 'react';
import { api } from '../api/integration';

interface UseAPIState {
  loading: boolean;
  error: string | null;
  data: any;
}

export const useAPI = () => {
  const [state, setState] = useState<UseAPIState>({
    loading: false,
    error: null,
    data: null
  });

  const execute = useCallback(async (apiCall: Promise<any>) => {
    setState({ loading: true, error: null, data: null });
    try {
      const result = await apiCall;
      setState({ loading: false, error: null, data: result.data });
      return result.data;
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message || 'API Error';
      setState({ loading: false, error: errorMsg, data: null });
      throw error;
    }
  }, []);

  // Thunder AI
  const queryAI = useCallback((candidateId: string, query: string) =>
    execute(api.queryAIConversation(candidateId, query)), [execute]);

  const getAIAssignment = useCallback((candidateId: string, roles: string[]) =>
    execute(api.getAIRecruiterAssignment(candidateId, roles)), [execute]);

  // Candidates
  const getCandidates = useCallback((filters?: any) =>
    execute(api.listCandidates(filters)), [execute]);

  const getCandidateScore = useCallback((candidateId: string) =>
    execute(api.getCandidateScore(candidateId)), [execute]);

  // Interviews
  const scheduleInterview = useCallback((candidateId: string, date: string, time: string) =>
    execute(api.addAvailabilitySlot(candidateId, date, time)), [execute]);

  const confirmInterview = useCallback((interviewId: string) =>
    execute(api.confirmInterview(interviewId, true)), [execute]);

  // Onboarding
  const startOnboarding = useCallback((employeeId: string) =>
    execute(api.startOnboarding(employeeId)), [execute]);

  // Resources
  const getResourcePool = useCallback((filters?: any) =>
    execute(api.getResourcePool(filters)), [execute]);

  const forecastDemand = useCallback((weeks?: number) =>
    execute(api.forecastDemand(weeks)), [execute]);

  return {
    ...state,
    // Thunder AI methods
    queryAI,
    getAIAssignment,
    // Candidate methods
    getCandidates,
    getCandidateScore,
    // Interview methods
    scheduleInterview,
    confirmInterview,
    // Onboarding methods
    startOnboarding,
    // Resource methods
    getResourcePool,
    forecastDemand,
    // Full API access
    api
  };
};

export default useAPI;
