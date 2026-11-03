// Line Type (CEO 2026-11-03: "Line Type should be updated in the entire system as direct from core").
// The stored value stays CORE / SPECIALITY (every rule and record keys on it); this is the one place
// that names them on screen.
export const LINE_TYPE_LABELS = { CORE: "Direct", SPECIALITY: "Speciality" };

export const lineTypeLabel = (value) => LINE_TYPE_LABELS[String(value || "").toUpperCase()] || value || "—";

export const LINE_TYPE_OPTIONS = Object.entries(LINE_TYPE_LABELS).map(([value, label]) => ({ value, label }));
