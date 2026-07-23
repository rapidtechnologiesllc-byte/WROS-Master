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

export const getAllEmployees = async () => {
  const { data } = await apiRequest("/employees", { method: "GET" });
  return data;
};

export const getBenchPool = async () => {
  const { data } = await apiRequest("/employees/bench-pool", { method: "GET" });
  return data;
};

export const getBenchAgingAlerts = async () => {
  const { data } = await apiRequest("/employees/bench-aging-alerts", { method: "GET" });
  return data;
};

export const getEmployeeById = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}`, { method: "GET" });
  return data;
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

export const getEmployeeBenchHistory = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}/bench-history`, {
    method: "GET",
  });
  return data;
};

// S-351/HRMS-0512 -- read-only Speciality/Core engine change audit trail.
export const getEngineHistory = async (employeeId) => {
  const { data } = await apiRequest(`/employees/${employeeId}/engine-history`, {
    method: "GET",
  });
  return data;
};

// HRMS-0708 minimal slice -- the MVP bridge from candidate to employee.
export const convertCandidateToEmployee = async (candidateId, payload) => {
  const { data } = await apiRequest(`/employees/convert-candidate/${candidateId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

// One-time bulk employee load from an .xlsx file.
export const bulkImportEmployees = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiRequest("/employees/bulk-import", {
    method: "POST",
    body: formData,
  });
  return data;
};
