const normalizeRole = (role) =>
  String(role || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "_");

export const ROLES = Object.freeze({
  SUPER_USER: "SUPER_USER",
  CANDIDATE: "CANDIDATE",
});

export const getNormalizedRole = (role) => normalizeRole(role);

export const isSuperUserRole = (role) =>
  normalizeRole(role) === ROLES.SUPER_USER;

export const isCandidateRole = (role) =>
  normalizeRole(role) === ROLES.CANDIDATE;

export const isCandidateUser = ({ role, userType }) =>
  isCandidateRole(role) ||
  String(userType || "")
    .trim()
    .toLowerCase() === "candidate";

export const canAccessFullHrms = ({ role }) => {
  return isSuperUserRole(role);
};

export const canAccessMyWorkspace = ({ permissionRole }) => {
  return (
    String(permissionRole || "")
      .trim()
      .toLowerCase() === "employee" || "HR Manager"
  );
};
