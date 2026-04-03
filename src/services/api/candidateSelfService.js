// Candidate self-service API wrappers.
import { apiRequest } from "./client";

export const getCandidateMyInfo = async () => {
  // Combined profile response (personal/education/experience/aadhar/pan).
  const { data } = await apiRequest("/candidate/my-info", {
    method: "GET",
    allow404: true
  });
  return data;
};

export const getCandidatePersonalInfo = async () => {
  // Personal info only (404 until first save — treat as empty).
  const { data } = await apiRequest("/candidate/personal-info", {
    method: "GET",
    allow404: true
  });
  return data;
};

export const getCandidateAadhar = async () => {
  // Aadhar form data (404 until first save — treat as empty).
  const { data } = await apiRequest("/candidate/aadhar", {
    method: "GET",
    allow404: true
  });
  return data;
};

export const getCandidatePan = async () => {
  // PAN form data (404 until first save — treat as empty).
  const { data } = await apiRequest("/candidate/pan", {
    method: "GET",
    allow404: true
  });
  return data;
};

export const getCandidateOnboardingStatus = async () => {
  // Completion status for onboarding forms.
  const { data } = await apiRequest("/candidate/onboarding-status", {
    method: "GET",
    allow404: true
  });
  return data;
};

export const changeCandidatePassword = async (payload) => {
  // Change candidate password after login.
  const { data } = await apiRequest("/candidate/change_password", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const submitCandidateInfoForm = async (payload) => {
  // Save personal info form.
  const { data } = await apiRequest("/candidate/candidate-form/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const submitCandidateEducationForm = async (educationRecords) => {
  // Bulk save education records.
  const { data } = await apiRequest("/candidate/education-form/", {
    method: "POST",
    body: JSON.stringify({
      education_records: educationRecords
    })
  });
  return data;
};

export const listCandidateEducation = async () => {
  // List education records with IDs (formID).
  const { data } = await apiRequest("/candidate/education/list", {
    method: "GET"
  });
  return data;
};

export const addCandidateEducation = async (payload) => {
  // Create single education record.
  const { data } = await apiRequest("/candidate/education/add", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const updateCandidateEducation = async (educationId, payload) => {
  // Update education record by ID.
  const { data } = await apiRequest(`/candidate/education/${educationId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

export const deleteCandidateEducation = async (educationId) => {
  // Delete education record by ID.
  const { data } = await apiRequest(`/candidate/education/${educationId}`, {
    method: "DELETE"
  });
  return data;
};

export const submitCandidateExperienceForm = async (experienceRecords) => {
  // Bulk save experience records.
  const { data } = await apiRequest("/candidate/experience-form/", {
    method: "POST",
    body: JSON.stringify({
      experience_records: experienceRecords
    })
  });
  return data;
};

export const listCandidateExperience = async () => {
  // List experience records with IDs (formID).
  const { data } = await apiRequest("/candidate/experience/list", {
    method: "GET"
  });
  return data;
};

export const addCandidateExperience = async (payload) => {
  // Create single experience record.
  const { data } = await apiRequest("/candidate/experience/add", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const updateCandidateExperience = async (experienceId, payload) => {
  // Update experience record by ID.
  const { data } = await apiRequest(`/candidate/experience/${experienceId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
  return data;
};

export const deleteCandidateExperience = async (experienceId) => {
  // Delete experience record by ID.
  const { data } = await apiRequest(`/candidate/experience/${experienceId}`, {
    method: "DELETE"
  });
  return data;
};

export const submitCandidateAadharForm = async (payload) => {
  // Save Aadhar details.
  const { data } = await apiRequest("/candidate/aadhar-form/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};

export const submitCandidatePanForm = async (payload) => {
  // Save PAN details.
  const { data } = await apiRequest("/candidate/pan-form/", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return data;
};
