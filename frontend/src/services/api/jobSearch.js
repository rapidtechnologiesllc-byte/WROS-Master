// Boolean search over candidates, each job's search criteria and captured candidates, saved searches and the
// team's skill synonyms (backend app/api/v1/endpoints/job_search.py).
import { apiRequest } from "./client";

const json = (method, payload) => ({ method, body: JSON.stringify(payload) });

export const searchCandidates = async ({ q, minExperienceYears, location, savedId, limit = 50 }) => {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (minExperienceYears !== "" && minExperienceYears != null) params.set("min_experience_years", String(minExperienceYears));
  if (location) params.set("location", location);
  if (savedId) params.set("saved_id", String(savedId));
  const { data } = await apiRequest(`/candidate-search?${params.toString()}`);
  return data;
};

export const listSavedSearches = async () => (await apiRequest("/candidate-search/saved")).data || [];

export const saveSearch = async (payload) => (await apiRequest("/candidate-search/saved", json("POST", payload))).data;

export const deleteSavedSearch = async (savedId) => {
  await apiRequest(`/candidate-search/saved/${savedId}`, { method: "DELETE" });
};

export const listSkillSynonyms = async () => (await apiRequest("/skill-synonyms")).data || [];

export const saveSkillSynonym = async (skill, otherNames) =>
  (await apiRequest("/skill-synonyms", json("PUT", { skill, other_names: otherNames }))).data;

export const deleteSkillSynonym = async (skill) => {
  await apiRequest(`/skill-synonyms/${encodeURIComponent(skill)}`, { method: "DELETE" });
};

export const getJobSearchCriteria = async (jobId) => (await apiRequest(`/jobs/${jobId}/search-criteria`)).data;

export const saveJobSearchCriteria = async (jobId, query) =>
  (await apiRequest(`/jobs/${jobId}/search-criteria`, json("PUT", { query }))).data;

export const resetJobSearchCriteria = async (jobId) =>
  (await apiRequest(`/jobs/${jobId}/search-criteria/reset`, { method: "POST" })).data;

export const listJobSearchMatches = async (jobId) => (await apiRequest(`/jobs/${jobId}/search-matches`)).data;

export const runJobSearchNow = async (jobId) =>
  (await apiRequest(`/jobs/${jobId}/search-matches/run`, { method: "POST" })).data;
