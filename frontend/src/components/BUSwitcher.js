// Top-bar business unit selector. What it lists comes from the user's role template, not a separate
// list (CEO 2026-11-02): the CEO and other org-level roles see every business unit and start on
// "All business units"; a partner sees the BUs they partner, a BU head the BUs they head, anyone
// else their own BU. Picking one narrows every screen to it; it never shows more than the role allows.
import { useEffect, useState } from "react";
import { Building2 } from "lucide-react";
import { getMyBUAccess, switchBU } from "../services/api/buContext";
import ScreenErrorDisplay from "./ScreenErrorDisplay";

const VIEW_KEY = "hrms_bu_view";
const ALL = "";

const label = (item) => (item.roles?.length ? `${item.name} · ${item.roles.join(", ")}` : item.name);

export default function BUSwitcher() {
  const [access, setAccess] = useState([]);
  const [canViewAll, setCanViewAll] = useState(false);
  const [activeId, setActiveId] = useState(ALL);
  const [loading, setLoading] = useState(true);
  const [screenError, setScreenError] = useState(null);

  useEffect(() => {
    // the old selector saved the user's own BU here and showed it as a restriction; drop it
    localStorage.removeItem("hrms_active_bu_id");
    getMyBUAccess()
      .then((res) => {
        setAccess(res.access || []);
        setCanViewAll(Boolean(res.can_view_all_bus));
        const chosen = res.active_business_unit_id;
        if (chosen == null && localStorage.getItem(VIEW_KEY)) {
          localStorage.removeItem(VIEW_KEY); // a stale choice outside the user's scope
        }
        setActiveId(chosen == null ? ALL : String(chosen));
      })
      .catch((err) => {
        console.error("[BUSwitcher] Failed to load business units:", err);
        setScreenError(`Could not load your business units: ${err.message}`);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleChange = async (e) => {
    const newId = e.target.value;
    try {
      if (newId === ALL) {
        localStorage.removeItem(VIEW_KEY);
      } else {
        await switchBU(Number(newId));
        localStorage.setItem(VIEW_KEY, newId);
      }
      setActiveId(newId);
      window.location.reload();
    } catch (err) {
      console.error("[BUSwitcher] Failed to switch business unit:", err);
      setScreenError(`Could not switch business unit: ${err.message}`);
    }
  };

  if (loading) return null;
  if (!canViewAll && access.length === 0) {
    return <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />;
  }

  if (!canViewAll && access.length === 1) {
    // one business unit: a label, never a dropdown with one option
    return (
      <>
        <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
        <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500" title={label(access[0])}>
          <Building2 className="h-3.5 w-3.5" />
          {label(access[0])}
        </div>
      </>
    );
  }

  return (
    <>
      <ScreenErrorDisplay error={screenError} onDismiss={() => setScreenError(null)} />
      <div className="flex items-center gap-1.5">
        <Building2 className="h-3.5 w-3.5 text-gray-500" />
        <select
          value={activeId}
          onChange={handleChange}
          aria-label="Business unit"
          className="text-xs font-medium border border-bx-border rounded-bx px-2 py-1 bg-white outline-none focus:border-bx-orange"
        >
          <option value={ALL}>{canViewAll ? "All business units" : "All my business units"}</option>
          {access.map((a) => (
            <option key={a.business_unit_id} value={String(a.business_unit_id)}>{label(a)}</option>
          ))}
        </select>
      </div>
    </>
  );
}
