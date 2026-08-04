// Help Desk/IT-HR Ticketing -- admin config for category->department
// routing + per-priority SLA policies. No hardcoded category list --
// an admin adds one row per real category, routed to ANY real
// department, covering every function per Avinash's explicit
// direction, not just HR/IT.
import { useEffect, useState } from "react";
import { Route, Timer } from "lucide-react";
import { toast } from "react-toastify";
import { Card, Button, Input, Select } from "../components/ui";
import { listDepartments } from "../services/api/rbac";
import {
  createRoutingRule, listRoutingRules, listSLAPolicies, updateSLAPolicy,
} from "../services/api/tickets";

export default function TicketRoutingAdminScreen() {
  const [routes, setRoutes] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [newRoute, setNewRoute] = useState({ category: "", subcategory: "", department_id: "" });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [r, d, p] = await Promise.all([listRoutingRules(), listDepartments(), listSLAPolicies()]);
      setRoutes(r || []);
      setDepartments(d || []);
      setPolicies(p || []);
    } catch (err) {
      toast.error("Could not load ticket routing configuration.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const addRoute = async (e) => {
    e.preventDefault();
    if (!newRoute.category.trim() || !newRoute.department_id) return;
    try {
      await createRoutingRule({
        category: newRoute.category.trim(),
        subcategory: newRoute.subcategory.trim() || null,
        department_id: Number(newRoute.department_id),
      });
      toast.success("Routing rule added.");
      setNewRoute({ category: "", subcategory: "", department_id: "" });
      load();
    } catch (err) {
      toast.error(err.message || "Could not add routing rule.");
    }
  };

  const savePolicy = async (priority, field, value) => {
    const policy = policies.find((p) => p.priority === priority);
    if (!policy) return;
    const updated = { ...policy, [field]: Number(value) };
    setPolicies(policies.map((p) => (p.priority === priority ? updated : p)));
    try {
      await updateSLAPolicy(priority, { response_minutes: updated.response_minutes, resolution_minutes: updated.resolution_minutes });
    } catch {
      toast.error(`Could not save ${priority} SLA policy.`);
    }
  };

  const deptOptions = [{ value: "", label: "Select department..." }, ...departments.map((d) => ({ value: String(d.id), label: d.name }))];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Ticket Routing & SLA</h1>
        <p className="text-sm text-gray-500">Category-to-department routing and response/resolution SLA targets for Help Desk tickets, org-wide.</p>
      </div>

      <Card title="Category Routing" subtitle="No fixed category list -- add a route for any category, to any department." icon={<Route size={16} />}>
        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : (
          <>
            <table className="w-full text-left mb-4 text-sm">
              <thead className="text-xs uppercase text-gray-500">
                <tr>
                  <th className="py-1.5 pr-3">Category</th>
                  <th className="py-1.5 pr-3">Subcategory</th>
                  <th className="py-1.5 pr-3">Department</th>
                </tr>
              </thead>
              <tbody>
                {routes.length === 0 ? (
                  <tr><td colSpan={3} className="py-3 text-gray-400">No routing rules configured yet -- tickets in unmatched categories go unassigned for manual triage.</td></tr>
                ) : (
                  routes.map((r) => (
                    <tr key={`${r.category}|${r.subcategory || ""}`} className="border-t border-gray-100">
                      <td className="py-1.5 pr-3">{r.category}</td>
                      <td className="py-1.5 pr-3 text-gray-500">{r.subcategory || "--"}</td>
                      <td className="py-1.5 pr-3">{departments.find((d) => d.id === r.department_id)?.name || r.department_id}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <form onSubmit={addRoute} className="flex flex-wrap items-end gap-3">
              <Input label="Category" value={newRoute.category} onChange={(v) => setNewRoute({ ...newRoute, category: v })} placeholder="e.g. Payroll Question" />
              <Input label="Subcategory (optional)" value={newRoute.subcategory} onChange={(v) => setNewRoute({ ...newRoute, subcategory: v })} />
              <Select label="Department" value={newRoute.department_id} onChange={(v) => setNewRoute({ ...newRoute, department_id: v })} options={deptOptions} />
              <Button type="submit">Add Route</Button>
            </form>
          </>
        )}
      </Card>

      <Card title="SLA Policies" subtitle="Response and resolution targets, in minutes, per priority tier." icon={<Timer size={16} />}>
        {!loading && (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-gray-500">
              <tr>
                <th className="py-1.5 pr-3">Priority</th>
                <th className="py-1.5 pr-3">Response (min)</th>
                <th className="py-1.5 pr-3">Resolution (min)</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.priority} className="border-t border-gray-100">
                  <td className="py-1.5 pr-3 font-medium">{p.priority}</td>
                  <td className="py-1.5 pr-3">
                    <input
                      type="number"
                      className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
                      value={p.response_minutes}
                      onChange={(e) => savePolicy(p.priority, "response_minutes", e.target.value)}
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      type="number"
                      className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
                      value={p.resolution_minutes}
                      onChange={(e) => savePolicy(p.priority, "resolution_minutes", e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
