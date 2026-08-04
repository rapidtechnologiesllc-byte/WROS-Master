// S-205/HRMS-0107 -- BU context switcher. Renders a real dropdown only
// for users with >1 bu_access row (AC-1); a single-BU user sees a
// static label, never a dropdown -- BR-0107-03's "no false affordance."
import { useEffect, useState } from "react";
import { Building2 } from "lucide-react";
import { toast } from "react-toastify";
import { activateAllBUsView, getMyBUAccess, switchBU } from "../services/api/buContext";

export default function BUSwitcher() {
  const [access, setAccess] = useState([]);
  const [canViewAllBUs, setCanViewAllBUs] = useState(false);
  const [activeId, setActiveId] = useState(localStorage.getItem("hrms_active_bu_id") || "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyBUAccess()
      .then((res) => {
        setAccess(res.access || []);
        setCanViewAllBUs(res.can_view_all_bus);
        if (!activeId && res.access?.length) {
          const def = res.access.find((a) => a.is_default) || res.access[0];
          setActiveId(String(def.business_unit_id));
          localStorage.setItem("hrms_active_bu_id", String(def.business_unit_id));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleChange = async (e) => {
    const newId = e.target.value;
    if (newId === "ALL") {
      try {
        await activateAllBUsView();
        localStorage.removeItem("hrms_active_bu_id");
        setActiveId("ALL");
        toast.info("Viewing all Business Units -- this is logged.");
        window.location.reload();
      } catch {
        toast.error("Could not activate the All BUs view.");
      }
      return;
    }
    try {
      await switchBU(Number(newId));
      localStorage.setItem("hrms_active_bu_id", newId);
      setActiveId(newId);
      toast.success("Business Unit switched.");
      window.location.reload();
    } catch {
      toast.error("Could not switch Business Unit.");
    }
  };

  if (loading || access.length === 0) return null;

  if (access.length === 1 && !canViewAllBUs) {
    // BR-0107-03 -- static label, never a dropdown with one option.
    return (
      <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
        <Building2 className="h-3.5 w-3.5" />
        {access[0].name}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <Building2 className="h-3.5 w-3.5 text-gray-500" />
      <select
        value={activeId}
        onChange={handleChange}
        className="text-xs font-medium border border-bx-border rounded-bx px-2 py-1 bg-white outline-none focus:border-bx-orange"
      >
        {access.map((a) => (
          <option key={a.business_unit_id} value={a.business_unit_id}>{a.name}</option>
        ))}
        {canViewAllBUs && <option value="ALL">All Business Units</option>}
      </select>
    </div>
  );
}
