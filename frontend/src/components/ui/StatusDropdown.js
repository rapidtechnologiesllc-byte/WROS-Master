import { useState } from "react";
import StatusBadge from "./StatusBadge";

const STATUS_OPTIONS = [
  "Sourced",
  "Applied",
  "Recruiter Screening",
  "L1 Interview",
  "Pre-Onboarding",
];

export default function StatusDropdown({ statusData, onChange }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(statusData?.pipeline_status);
  const [comment, setComment] = useState("");

  const handleMove = () => {
    if (selected !== statusData.pipeline_status) {
      onChange({ status: selected, comment });
    }
    setOpen(false);
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      {statusData?.pipeline_status && (
        <div>
          <StatusBadge type="pipeline" value={statusData.pipeline_status} />
        </div>
      )}

      {open && (
        <div
          style={{
            position: "absolute",
            top: "40px",
            right: 0,
            width: "260px",
            background: "#fff",
            border: "1px solid #ddd",
            borderRadius: "8px",
            padding: "16px",
            boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            zIndex: 10,
          }}
        >
          <p style={{ fontSize: "12px", color: "#666" }}>
            SELECT STAGE TO MOVE
          </p>

          {STATUS_OPTIONS.map((status) => (
            <label
              key={status}
              style={{ display: "block", marginBottom: "8px" }}
            >
              <input
                type="radio"
                name="status"
                value={status}
                checked={selected === status}
                onChange={() => setSelected(status)}
                disabled={status === statusData.pipeline_status}
              />
              <span style={{ marginLeft: "8px" }}>{status}</span>
            </label>
          ))}
          {selected !== "Preboarding" ? (
            <textarea
              placeholder="Write comment (optional)"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{
                width: "100%",
                marginTop: "10px",
                padding: "8px",
                borderRadius: "4px",
                border: "1px solid #ccc",
              }}
            />
          ) : null}
          <button
            onClick={handleMove}
            style={{
              marginTop: "12px",
              width: "100%",
              background: "#1a73e8",
              color: "#fff",
              border: "none",
              padding: "10px",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            Move
          </button>
        </div>
      )}
    </div>
  );
}
