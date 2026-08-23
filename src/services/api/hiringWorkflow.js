import { apiRequest } from "./client";

export async function getPanelistSuggestions(demandId, level = "L1") {
  const res = await apiRequest(`/hiring-workflow/suggestions/${demandId}/panelists`, {
    method: "GET",
    params: { level },
  });
  return res.data?.data;
}

export async function checkL1ToL2Trigger(interviewId) {
  const res = await apiRequest(`/hiring-workflow/interviews/${interviewId}/l1-to-l2-trigger`);
  return res.data?.data;
}

export async function checkAffordability(submissionId, buId = null) {
  const res = await apiRequest(`/hiring-workflow/submissions/${submissionId}/affordability`, {
    method: "GET",
    params: buId ? { bu_id: buId } : {},
  });
  return res.data?.data;
}

export async function createL2Panel(demandId, submissionId, panelists) {
  const res = await apiRequest(`/hiring-workflow/interviews/${demandId}/create-l2-panel`, {
    method: "POST",
    data: { submission_id: submissionId, panelists },
  });
  return res.data?.data;
}

export async function recordNoShow(interviewId) {
  const res = await apiRequest(`/hiring-workflow/interviews/${interviewId}/no-show`, {
    method: "POST",
  });
  return res.data?.data;
}
