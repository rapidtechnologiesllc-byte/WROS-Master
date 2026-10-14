// S-245 (Create Employee Profile) + S-246 (Mark Employee as Bench) +
// S-247 (View Bench Pool) + S-248 (Bench Aging Report).
import { apiRequest } from "./client";

export const createEmployee = async (payload) => {
  const { data } = await apiRequest("/employees", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

// 2026-08-12: unwrapped here (same fix and same reason as getAllUsers()
// in services/api/users.js) -- backend returns {employees: [...]}, this
// now always returns a plain array so callers don't each re-unwrap it.
export const getAllEmployees = async () => {
  const { data } = await apiRequest("/employees", { method: "GET" });
  return data?.employees || [];
};







export const markEmployeeOnBench = async (employeeId, reason) => {
  const { data } = await apiRequest(`/employees/${employeeId}/mark-bench`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return data;
};

export const removeEmployeeFromBench = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}/remove-from-bench`, {
    method: "POST",
  });
  return data;
};










// S-DEFECT-1: Update employee certifications (Guidewire certification levels)
// Employer company (BX-US / BX-IN) and business unit; "" / null clears
export const updateEmployeeOrganization = async (employeeId, organization) => {
  const { data } = await apiRequest(`/employees/${employeeId}/organization`, {
    method: "PUT",
    body: JSON.stringify(organization),
  });
  return data;
};

export const updateEmployeeCertifications = async (employeeId, certifications) => {
  const { data } = await apiRequest(`/employees/${employeeId}/certifications`, {
    method: "PUT",
    body: JSON.stringify(certifications),
  });
  return data;
};

// Escalations: an open one keeps the employee away from every client; a Director resolves it.
export const getEmployeeEscalations = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}/escalations`, { method: "GET" });
  return data;
};

export const raiseEmployeeEscalation = async (employeeId, { reason, severity }) => {
  const { data } = await apiRequest(`/employees/${employeeId}/escalations`, {
    method: "POST",
    body: JSON.stringify({ reason, severity }),
  });
  return data;
};

export const resolveEmployeeEscalation = async (escalationId, resolutionNote) => {
  const { data } = await apiRequest(`/employees/escalations/${escalationId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_note: resolutionNote }),
  });
  return data;
};
