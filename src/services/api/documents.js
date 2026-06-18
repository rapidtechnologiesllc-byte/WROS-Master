// Document upload helpers (resume and candidate documents).
import {
  getApiBaseUrl,
  apiRequest,
  maybeRedirectOnUnauthorized,
} from "./client";

const _uploadDocument = async (path, file, token) => {
  if (!file) throw new Error("File is required.");
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    const message = data?.detail || data?.message || "Upload failed.";
    throw new Error(message);
  }

  return data;
};

export const uploadResume = async ({ candidateId, file }) => {
  if (!candidateId)
    throw new Error("Candidate ID is required for resume upload.");
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument(
    `/documents/upload/resume?candidate_id=${encodeURIComponent(candidateId)}`,
    file,
    token,
  );
};

export const uploadPan = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/pan", file, token);
};

export const uploadAadhar = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/aadhar", file, token);
};

export const uploadEducationCertificate = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/education", file, token);
};

export const uploadExperienceLetter = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/experience", file, token);
};

export const uploadSalarySlip = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/salary-slip", file, token);
};

export const uploadBankStatement = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/bank-statement", file, token);
};
export const uploadUanPfDocument = async (file) => {
  const token = localStorage.getItem("hrms_token");
  return _uploadDocument("/documents/upload/uan-pf", file, token);
};

export const getCandidateDocuments = async (candidateId) => {
  const { data } = await apiRequest(`/documents/candidate/${candidateId}`, {
    method: "GET",
  });
  return data;
};

export const verifyDocument = async (
  candidateId,
  documentType,
  isVerified,
  notes,
) => {
  const params = new URLSearchParams();
  params.set("is_verified", String(isVerified));
  if (notes) params.set("notes", notes);
  const { data } = await apiRequest(
    `/documents/verify/${candidateId}/${documentType}?${params.toString()}`,
    { method: "PATCH" },
  );
  return data;
};

// Candidate endpoint: list documents uploaded by the authenticated candidate.
export const getMyDocuments = async () => {
  const { data } = await apiRequest("/documents/my-documents", {
    method: "GET",
    allow404: true,
    // Some environments still gate this endpoint with HR-only permission.
    // Treat 401 as "no documents yet" so candidate portal does not auto-logout.
    allowStatuses: [401],
  });
  return data;
};

// Streams a document from SharePoint for inline viewing.
// Returns a Blob so callers can open in a new tab.
export const viewDocument = async (documentId) => {
  const token = localStorage.getItem("hrms_token");
  const response = await fetch(
    `${getApiBaseUrl()}/documents/${encodeURIComponent(documentId)}/view`,
    {
      method: "GET",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    },
  );

  if (!response.ok) {
    if (maybeRedirectOnUnauthorized(response)) {
      throw new Error("Your session has expired. Please sign in again.");
    }
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const message = data?.detail || data?.message || "Document view failed.";
    throw new Error(message);
  }

  const blob = await response.blob();
  const contentType =
    response.headers.get("content-type") || "application/octet-stream";
  return { blob, contentType };
};
