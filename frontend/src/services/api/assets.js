// Asset ledger (CEO 2026-11-10): every device the organisation holds or is responsible for, owned by the
// IT Admin function. The server holds every rule; a refused action comes back with the reason.
import { apiRequest } from "./client";

const post = (path, body) => apiRequest(path, { method: "POST", body: JSON.stringify(body || {}) }).then((r) => r.data);

export const getAssetOptions = () => apiRequest("/assets/options").then((r) => r.data);

export const listAssets = (filters = {}) => {
  const query = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  const suffix = query.toString() ? `?${query}` : "";
  return apiRequest(`/assets${suffix}`).then((r) => {
    if (!r.data || !Array.isArray(r.data.assets)) throw new Error("Unexpected response: no asset list.");
    return r.data;
  });
};

export const getAssetAlerts = () => apiRequest("/assets/alerts").then((r) => r.data?.alerts || []);
export const getAsset = (assetId) => apiRequest(`/assets/${assetId}`).then((r) => r.data);
export const registerAsset = (body) => post("/assets", body);
export const updateAsset = (assetId, body) =>
  apiRequest(`/assets/${assetId}`, { method: "PATCH", body: JSON.stringify(body) }).then((r) => r.data);

export const issueAsset = (assetId, body) => post(`/assets/${assetId}/issue-to-employee`, body);
export const confirmAssetReceipt = (assetId, body) => post(`/assets/${assetId}/confirm-receipt`, body);
export const requestAssetReturn = (assetId, body) => post(`/assets/${assetId}/request-return`, body);
export const recordReturnShipment = (assetId, body) => post(`/assets/${assetId}/return-shipment`, body);
export const receiveAssetReturn = (assetId, body) => post(`/assets/${assetId}/receive-return`, body);
export const returnAssetToOwner = (assetId, body) => post(`/assets/${assetId}/return-to-owner`, body);
export const confirmOwnerReceived = (assetId, body) => post(`/assets/${assetId}/owner-received`, body);
export const reportAssetDefect = (assetId, body) => post(`/assets/${assetId}/issues`, body);
export const updateAssetDefect = (issueId, body) => post(`/assets/issues/${issueId}`, body);
export const markAssetLost = (assetId, note) => post(`/assets/${assetId}/lost`, { note });
export const retireAsset = (assetId, note) => post(`/assets/${assetId}/retire`, { note });

export const getEmployeeAssets = (employeeId) => apiRequest(`/assets/employee/${employeeId}`).then((r) => r.data);
export const signOffClearance = (employeeId, note) => post(`/assets/employee/${employeeId}/clearance/sign-off`, { note });

export const getProjectKit = (projectId) => apiRequest(`/assets/project/${projectId}/requirements`).then((r) => r.data);
export const setProjectKit = (projectId, items) =>
  apiRequest(`/assets/project/${projectId}/requirements`, { method: "PUT", body: JSON.stringify({ items }) })
    .then((r) => r.data);

export const titleCase = (value) =>
  (value || "").toLowerCase().split("_").map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w)).join(" ");
