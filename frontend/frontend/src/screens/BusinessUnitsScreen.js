import { useState, useEffect } from "react";
import { Edit2, Plus, Trash2, Save, X } from "lucide-react";

export default function BusinessUnitsScreen() {
  const [businessUnits, setBusinessUnits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    bu_code: "",
    description: "",
  });

  useEffect(() => {
    loadBusinessUnits();
  }, []);

  const loadBusinessUnits = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/business-units", {
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setBusinessUnits(Array.isArray(data) ? data : data.business_units || []);
      }
    } catch (error) {
      console.error("Failed to load business units:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddNew = () => {
    setFormData({ name: "", bu_code: "", description: "" });
    setIsAddingNew(true);
  };

  const handleEdit = (bu) => {
    setFormData({
      name: bu.name || bu.bu_name || "",
      bu_code: bu.bu_code || "",
      description: bu.description || "",
    });
    setEditingId(bu.id);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      alert("Business Unit name is required");
      return;
    }

    try {
      const method = isAddingNew ? "POST" : "PATCH";
      const url = isAddingNew ? "/api/business-units" : `/api/business-units/${editingId}`;

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        alert("Business Unit saved successfully");
        setIsAddingNew(false);
        setEditingId(null);
        loadBusinessUnits();
      }
    } catch (error) {
      console.error("Failed to save business unit:", error);
      alert("Failed to save Business Unit");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this Business Unit?")) return;

    try {
      const response = await fetch(`/api/business-units/${id}`, {
        method: "DELETE",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      if (response.ok) {
        alert("Business Unit deleted successfully");
        loadBusinessUnits();
      }
    } catch (error) {
      console.error("Failed to delete business unit:", error);
      alert("Failed to delete Business Unit");
    }
  };

  const handleCancel = () => {
    setIsAddingNew(false);
    setEditingId(null);
    setFormData({ name: "", bu_code: "", description: "" });
  };

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Business Units</h1>
        <p className="text-gray-600 mt-1">Manage organization-wide Business Units for candidate and employee BU scoping</p>
      </div>

      {isAddingNew || editingId ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {isAddingNew ? "Create Business Unit" : "Edit Business Unit"}
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Business Unit Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., North America"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Code
                </label>
                <input
                  type="text"
                  value={formData.bu_code}
                  onChange={(e) => setFormData({ ...formData, bu_code: e.target.value })}
                  placeholder="e.g., NA"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="e.g., North American operations"
                rows={3}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>
          </div>

          <div className="border-t pt-4 mt-4 flex gap-3 justify-end">
            <button
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium text-sm flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={handleAddNew}
          className="mb-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium text-sm flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Business Unit
        </button>
      )}

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading Business Units...</div>
      ) : businessUnits.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center">
          <p className="text-gray-600">No Business Units found. Create one to get started.</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-900">Name</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-900">Code</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-900">Description</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-900">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {businessUnits.map((bu) => (
                <tr key={bu.id} className="hover:bg-gray-50 transition">
                  <td className="px-6 py-3 text-sm text-gray-900">{bu.name || bu.bu_name}</td>
                  <td className="px-6 py-3 text-sm text-gray-600">{bu.bu_code || "—"}</td>
                  <td className="px-6 py-3 text-sm text-gray-600">{bu.description || "—"}</td>
                  <td className="px-6 py-3 text-sm">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(bu)}
                        className="p-1 text-blue-600 hover:bg-blue-50 rounded transition"
                        title="Edit"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(bu.id)}
                        className="p-1 text-red-600 hover:bg-red-50 rounded transition"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
