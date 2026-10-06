// Business-unit picker for BU-scoped dashboards (BU Head, Partner). Shown
// when the API answers status "needs_business_unit" -- the user (e.g.
// Admin) has no BU of their own, so they choose which BU to view.
import { Link } from "react-router-dom";
import { Building2 } from "lucide-react";
import { Card, Select } from "./ui";

export default function DashboardBUPicker({ businessUnits, value, onChange }) {
  if (!businessUnits?.length) {
    return (
      <Card>
        <div className="flex items-start gap-3 p-2">
          <Building2 className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="text-sm text-gray-700">
            No business units exist yet. Create one in{" "}
            <Link className="text-blue-600 hover:underline" to="/admin/users-access-control/business-units">
              Users &amp; Access Control → Business Units
            </Link>{" "}
            to see this dashboard.
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="max-w-sm">
      <Select
        label="Business unit"
        value={value ?? ""}
        onChange={(v) => onChange(v ? Number(v) : null)}
        options={[
          { value: "", label: "Select a business unit..." },
          ...businessUnits.map((bu) => ({ value: String(bu.id), label: bu.name })),
        ]}
      />
    </div>
  );
}
