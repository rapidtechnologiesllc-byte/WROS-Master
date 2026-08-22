import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { apiRequest } from "../../services/api/client";
import { Plus, Edit2, Trash2, Building2, MapPin } from "lucide-react";
import { ROUTES } from "../../utils/Routes";

const POSITIONS = [
  { id: 1, name: "CEO" },
  { id: 2, name: "Partner" },
  { id: 3, name: "BU Head" },
  { id: 4, name: "Senior Director" },
  { id: 5, name: "Director" },
  { id: 6, name: "Technical Manager" },
  { id: 7, name: "Senior Manager" },
  { id: 8, name: "Manager" },
  { id: 9, name: "Team Lead" },
  { id: 10, name: "Senior Consultant" }
];

export default function OrganizationSection({ orgTab = "business-units" }) {
  const navigate = useNavigate();
  const [businessUnits, setBusinessUnits] = useState([]);
  const [deliveryCenters, setDeliveryCenters] = useState([
    { id: 1, name: "Austin, TX", type: "HQ", buServed: ["North America"], headcount: 150 },
    { id: 2, name: "Youngstown, OH", type: "Delivery", buServed: ["North America"], headcount: 300 },
  ]);
  const [showAddBUModal, setShowAddBUModal] = useState(false);
  const [newBUName, setNewBUName] = useState("");
  const [newBUDescription, setNewBUDescription] = useState("");
  const [isSubmittingBU, setIsSubmittingBU] = useState(false);
  const [editingBUId, setEditingBUId] = useState(null);
  const [editBUName, setEditBUName] = useState("");
  const [editBUDescription, setEditBUDescription] = useState("");
  const [newBUPartner, setNewBUPartner] = useState("");
  const [newBUBUHead, setNewBUBUHead] = useState("");
  const [newBURegion, setNewBURegion] = useState("");
  const [newBUContinent, setNewBUContinent] = useState("");
  const [editBUPartner, setEditBUPartner] = useState("");
  const [editBUBUHead, setEditBUBUHead] = useState("");
  const [editBURegion, setEditBURegion] = useState("");
  const [editBUContinent, setEditBUContinent] = useState("");

  // Positions management state
  const [positions, setPositions] = useState(POSITIONS);
  const [showAddPositionModal, setShowAddPositionModal] = useState(false);
  const [newPositionName, setNewPositionName] = useState("");
  const [showPositionsManager, setShowPositionsManager] = useState(false);

  // Organizational Hierarchy state
  const [orgNodes, setOrgNodes] = useState([]);
  const [showAddOrgNodeModal, setShowAddOrgNodeModal] = useState(false);
  const [newOrgNodeEmployeeName, setNewOrgNodeEmployeeName] = useState("");
  const [newOrgNodePosition, setNewOrgNodePosition] = useState("");
  const [newOrgNodeReportsTo, setNewOrgNodeReportsTo] = useState("");
  const [newOrgNodeBusinessUnit, setNewOrgNodeBusinessUnit] = useState("");
  const [newOrgNodeLocation, setNewOrgNodeLocation] = useState("");
  const [isSubmittingOrgNode, setIsSubmittingOrgNode] = useState(false);
  const [editingOrgNodeId, setEditingOrgNodeId] = useState(null);
  const [editOrgNodeEmployeeName, setEditOrgNodeEmployeeName] = useState("");
  const [editOrgNodePosition, setEditOrgNodePosition] = useState("");
  const [editOrgNodeReportsTo, setEditOrgNodeReportsTo] = useState("");
  const [editOrgNodeBusinessUnit, setEditOrgNodeBusinessUnit] = useState("");
  const [editOrgNodeLocation, setEditOrgNodeLocation] = useState("");

  // Load business units from database via API
  useEffect(() => {
    const loadBusinessUnits = async () => {
      try {
        const { data } = await apiRequest("/bu-context/available-buses", {
          skipAuth: true,
          method: "GET"
        });
        const busData = data?.business_units || [];
        setBusinessUnits(busData);
      } catch (err) {
        console.error("Failed to load business units:", err);
        setBusinessUnits([]);
      }
    };
    loadBusinessUnits();
  }, []);

  // Load organizational nodes from database via API
  useEffect(() => {
    const loadOrgNodes = async () => {
      try {
        const { data } = await apiRequest("/org/nodes");
        setOrgNodes(Array.isArray(data) ? data : data?.org_nodes || []);
      } catch (err) {
        console.error("Failed to load org nodes:", err);
        setOrgNodes([]);
      }
    };
    loadOrgNodes();
  }, []);

  const handleAddBusinessUnit = async (e) => {
    e.preventDefault();
    if (!newBUName.trim()) {
      toast.error("Business Unit Name is required");
      return;
    }
    if (!newBUPartner) {
      toast.error("Partner is required");
      return;
    }
    if (!newBUBUHead) {
      toast.error("BU Head is required");
      return;
    }

    setIsSubmittingBU(true);
    try {
      const payload = {
        name: newBUName.trim(),
        description: newBUDescription.trim() || null,
        partner_id: parseInt(newBUPartner, 10),
        bu_head_id: parseInt(newBUBUHead, 10),
        ...(newBURegion && { region: newBURegion.trim() }),
        ...(newBUContinent && { continent: newBUContinent.trim() }),
      };

      await apiRequest("/rbac/business-units", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      toast.success("Business Unit created successfully");

      // Refresh business units list
      const { data } = await apiRequest("/bu-context/available-buses", {
        skipAuth: true,
        method: "GET"
      });
      const busData = data?.business_units || [];
      setBusinessUnits(busData);

      // Close modal and reset form
      setShowAddBUModal(false);
      setNewBUName("");
      setNewBUDescription("");
      setNewBUPartner("");
      setNewBUBUHead("");
      setNewBURegion("");
      setNewBUContinent("");
    } catch (err) {
      console.error("Failed to add business unit:", err);
      toast.error(err?.message || "Failed to add business unit");
    } finally {
      setIsSubmittingBU(false);
    }
  };

  const handleEditBusinessUnit = (bu) => {
    setEditingBUId(bu.id);
    setEditBUName(bu.name || bu.bu_name || "");
    setEditBUDescription(bu.description || "");
    setEditBUPartner(bu.partner_id ? String(bu.partner_id) : "");
    setEditBUBUHead(bu.bu_head_id ? String(bu.bu_head_id) : "");
    setEditBURegion(bu.region || "");
    setEditBUContinent(bu.continent || "");
  };

  const handleSaveEditedBusinessUnit = async () => {
    if (!editBUName.trim()) {
      toast.error("Business Unit Name is required");
      return;
    }
    if (!editBUPartner) {
      toast.error("Partner is required");
      return;
    }
    if (!editBUBUHead) {
      toast.error("BU Head is required");
      return;
    }
    try {
      await apiRequest(`/rbac/business-units/${editingBUId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editBUName.trim(),
          description: editBUDescription.trim() || null,
          partner_id: parseInt(editBUPartner, 10),
          bu_head_id: parseInt(editBUBUHead, 10),
          ...(editBURegion && { region: editBURegion.trim() }),
          ...(editBUContinent && { continent: editBUContinent.trim() }),
        }),
      });
      // Refresh business units list
      const { data } = await apiRequest("/bu-context/available-buses", {
        skipAuth: true,
        method: "GET"
      });
      const busData = data?.business_units || [];
      setBusinessUnits(busData);
      setEditingBUId(null);
      setEditBUName("");
      setEditBUDescription("");
      setEditBUPartner("");
      setEditBUBUHead("");
      setEditBURegion("");
      setEditBUContinent("");
      toast.success("Business Unit updated successfully");
    } catch (err) {
      console.error("Failed to update business unit:", err);
      toast.error(err?.message || "Failed to update business unit");
    }
  };

  const handleDeleteBusinessUnit = async (buId) => {
    if (!window.confirm("Are you sure you want to delete this business unit?")) {
      return;
    }
    try {
      await apiRequest(`/rbac/business-units/${buId}`, {
        method: "DELETE",
      });
      // Refresh business units list
      const { data } = await apiRequest("/bu-context/available-buses", {
        skipAuth: true,
        method: "GET"
      });
      const busData = data?.business_units || [];
      setBusinessUnits(busData);
      toast.success("Business Unit deleted successfully");
    } catch (err) {
      console.error("Failed to delete business unit:", err);
      toast.error("Failed to delete business unit");
    }
  };

  const handleAddPosition = (e) => {
    e.preventDefault();
    if (newPositionName.trim()) {
      const newPos = {
        id: Math.max(...positions.map(p => p.id), 0) + 1,
        name: newPositionName
      };
      setPositions([...positions, newPos]);
      setNewPositionName("");
      setShowAddPositionModal(false);
    }
  };

  const handleDeletePosition = (posId) => {
    if (positions.length <= 1) {
      alert("You must have at least one position");
      return;
    }
    setPositions(positions.filter(p => p.id !== posId));
  };

  const handleAddOrgNode = async (e) => {
    e.preventDefault();
    if (newOrgNodeEmployeeName.trim() && newOrgNodePosition.trim()) {
      setIsSubmittingOrgNode(true);
      try {
        const payload = {
          employee_name: newOrgNodeEmployeeName,
          position_id: parseInt(newOrgNodePosition),
          reports_to: newOrgNodeReportsTo || null,
          business_unit: newOrgNodeBusinessUnit || null,
          location: newOrgNodeLocation || null
        };

        const { data } = await apiRequest("/org/nodes", "POST", payload);

        if (data && data.id) {
          setOrgNodes([...orgNodes, data]);
          toast.success("Org node created successfully");

          // Reset form after successful submission
          setNewOrgNodeEmployeeName("");
          setNewOrgNodePosition("");
          setNewOrgNodeReportsTo("");
          setNewOrgNodeBusinessUnit("");
          setNewOrgNodeLocation("");
          setShowAddOrgNodeModal(false);
        }
      } catch (error) {
        console.error("Error creating org node:", error);
        toast.error(error?.message || "Failed to create org node");
      } finally {
        setIsSubmittingOrgNode(false);
      }
    }
  };

  const handleEditOrgNode = (node) => {
    setEditingOrgNodeId(node.id);
    setEditOrgNodeEmployeeName(node.employeeName);
    setEditOrgNodePosition(node.position.toString());
    setEditOrgNodeReportsTo(node.reportsTo ? node.reportsTo.toString() : "");
    setEditOrgNodeBusinessUnit(node.businessUnit || "");
    setEditOrgNodeLocation(node.location || "");
  };

  const handleSaveEditedOrgNode = () => {
    if (!editOrgNodeEmployeeName.trim() || !editOrgNodePosition.trim()) {
      return;
    }
    setOrgNodes(orgNodes.map(node =>
      node.id === editingOrgNodeId
        ? {
            ...node,
            employeeName: editOrgNodeEmployeeName,
            position: parseInt(editOrgNodePosition),
            reportsTo: editOrgNodeReportsTo ? parseInt(editOrgNodeReportsTo) : null,
            businessUnit: editOrgNodeBusinessUnit,
            location: editOrgNodeLocation
          }
        : node
    ));
    setEditingOrgNodeId(null);
    setEditOrgNodeEmployeeName("");
    setEditOrgNodePosition("");
    setEditOrgNodeReportsTo("");
    setEditOrgNodeBusinessUnit("");
    setEditOrgNodeLocation("");
  };

  const handleDeleteOrgNode = (nodeId) => {
    if (window.confirm("Are you sure you want to remove this person from the organizational hierarchy?")) {
      setOrgNodes(orgNodes.filter(n => n.id !== nodeId));
    }
  };

  const getPositionName = (positionId) => {
    return positions.find(p => p.id === positionId)?.name || "Unknown";
  };

  const getBusinessUnitName = (buId) => {
    return businessUnits.find(bu => bu.id === buId)?.name || "-";
  };

  const getReportingManagerName = (nodeReportsTo) => {
    const reportingNode = orgNodes.find(n => n.id === nodeReportsTo);
    if (reportingNode) {
      return reportingNode.employeeName;
    }
    return "CEO";
  };

  return (
    <div className="space-y-6">
      {/* Tabs - Link to URL-based sections */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          onClick={() => navigate(ROUTES.ADMIN_SETTINGS_ORGANIZATION_BUSINESS_UNITS)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "business-units"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          <Building2 className="inline h-4 w-4 mr-2" />
          Business Units
        </button>
        <button
          onClick={() => navigate(ROUTES.ADMIN_SETTINGS_ORGANIZATION_DELIVERY_CENTERS)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "delivery-centers"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          <MapPin className="inline h-4 w-4 mr-2" />
          Delivery Centers
        </button>
        <button
          onClick={() => navigate(ROUTES.ADMIN_SETTINGS_ORGANIZATION_HIERARCHY)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            orgTab === "hierarchy"
              ? "border-bx-orange text-bx-orange"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          Organizational Hierarchy
        </button>
      </div>

      {/* Business Units Tab */}
      {orgTab === "business-units" && (
        <div className="space-y-4">
          <button
            onClick={() => setShowAddBUModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium">
            <Plus className="h-4 w-4" />
            Add Business Unit
          </button>
          <div className="space-y-3">
            {businessUnits.map((bu) => (
              <div key={bu.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
                <div className="flex-1">
                  <h4 className="font-semibold text-gray-900">{bu.name}</h4>
                  <div className="grid grid-cols-3 gap-4 mt-2 text-sm text-gray-600">
                    <div><span className="font-medium">Region:</span> {bu.region || "-"}</div>
                    <div><span className="font-medium">Continent:</span> {bu.continent || "-"}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEditBusinessUnit(bu)}
                    className="p-2 text-blue-600 hover:bg-blue-50 rounded"
                    title="Edit Business Unit">
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteBusinessUnit(bu.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded"
                    title="Delete Business Unit">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add Business Unit Modal */}
      {showAddBUModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Add Business Unit</h3>
              <button
                onClick={() => setShowAddBUModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleAddBusinessUnit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Unit Name *
                </label>
                <input
                  type="text"
                  value={newBUName}
                  onChange={(e) => setNewBUName(e.target.value)}
                  placeholder="e.g., Asia Pacific"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (Optional)
                </label>
                <textarea
                  value={newBUDescription}
                  onChange={(e) => setNewBUDescription(e.target.value)}
                  placeholder="Add a description..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  rows="3"
                  disabled={isSubmittingBU}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Partner *
                </label>
                <select
                  value={newBUPartner}
                  onChange={(e) => setNewBUPartner(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                >
                  <option value="">Select a Partner...</option>
                  {orgNodes
                    .filter((node) => node.position_id === 2)
                    .map((partner) => (
                      <option key={partner.id} value={partner.id}>
                        {partner.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  BU Head *
                </label>
                <select
                  value={newBUBUHead}
                  onChange={(e) => setNewBUBUHead(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                >
                  <option value="">Select a BU Head...</option>
                  {orgNodes
                    .filter((node) => node.position_id === 3)
                    .map((head) => (
                      <option key={head.id} value={head.id}>
                        {head.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Region (Optional)
                </label>
                <input
                  type="text"
                  value={newBURegion}
                  onChange={(e) => setNewBURegion(e.target.value)}
                  placeholder="e.g., Asia, Europe, North America"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Continent (Optional)
                </label>
                <input
                  type="text"
                  value={newBUContinent}
                  onChange={(e) => setNewBUContinent(e.target.value)}
                  placeholder="e.g., Asia, Europe, North America"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  disabled={isSubmittingBU}
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddBUModal(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                  disabled={isSubmittingBU}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                  disabled={!newBUName.trim() || isSubmittingBU}
                >
                  {isSubmittingBU ? "Adding..." : "Add Business Unit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Business Unit Modal */}
      {editingBUId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Edit Business Unit</h3>
              <button
                onClick={() => setEditingBUId(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveEditedBusinessUnit(); }} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Unit Name *
                </label>
                <input
                  type="text"
                  value={editBUName}
                  onChange={(e) => setEditBUName(e.target.value)}
                  placeholder="e.g., Asia Pacific"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (Optional)
                </label>
                <textarea
                  value={editBUDescription}
                  onChange={(e) => setEditBUDescription(e.target.value)}
                  placeholder="Add a description..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  rows="3"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Partner *
                </label>
                <select
                  value={editBUPartner}
                  onChange={(e) => setEditBUPartner(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select a Partner...</option>
                  {orgNodes
                    .filter((node) => node.position_id === 2)
                    .map((partner) => (
                      <option key={partner.id} value={partner.id}>
                        {partner.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  BU Head *
                </label>
                <select
                  value={editBUBUHead}
                  onChange={(e) => setEditBUBUHead(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select a BU Head...</option>
                  {orgNodes
                    .filter((node) => node.position_id === 3)
                    .map((head) => (
                      <option key={head.id} value={head.id}>
                        {head.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Region (Optional)
                </label>
                <input
                  type="text"
                  value={editBURegion}
                  onChange={(e) => setEditBURegion(e.target.value)}
                  placeholder="e.g., Asia, Europe, North America"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Continent (Optional)
                </label>
                <input
                  type="text"
                  value={editBUContinent}
                  onChange={(e) => setEditBUContinent(e.target.value)}
                  placeholder="e.g., Asia, Europe, North America"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setEditingBUId(null)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                  disabled={!editBUName.trim()}
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delivery Centers Tab */}
      {orgTab === "delivery-centers" && (
        <div className="space-y-4">
          <button className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium">
            <Plus className="h-4 w-4" />
            Add Delivery Center
          </button>
          <div className="space-y-3">
            {deliveryCenters.map((dc) => (
              <div key={dc.id} className="border border-gray-200 rounded-lg p-4 flex items-start justify-between hover:bg-gray-50">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h4 className="font-semibold text-gray-900">{dc.name}</h4>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      dc.type === "HQ"
                        ? "bg-purple-100 text-purple-800"
                        : "bg-blue-100 text-blue-800"
                    }`}>
                      {dc.type}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mt-2 text-sm text-gray-600">
                    <div><span className="font-medium">Serves:</span> {dc.buServed.join(", ")}</div>
                    <div><span className="font-medium">Headcount:</span> {dc.headcount}</div>
                    <div><span className="font-medium">Type:</span> {dc.type === "HQ" ? "Headquarters" : "Delivery Center"}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="p-2 text-blue-600 hover:bg-blue-50 rounded"><Edit2 className="h-4 w-4" /></button>
                  <button className="p-2 text-red-600 hover:bg-red-50 rounded"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hierarchy Tab */}
      {orgTab === "hierarchy" && (
        <div className="space-y-4">
          <div className="flex gap-2">
            <button
              onClick={() => setShowAddOrgNodeModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover text-sm font-medium">
              <Plus className="h-4 w-4" />
              Add Org Node
            </button>
            <button
              onClick={() => setShowPositionsManager(!showPositionsManager)}
              className="flex items-center gap-2 px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">
              Manage Positions
            </button>
          </div>

          {/* Positions Manager - Collapsible */}
          {showPositionsManager && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
              <div className="flex justify-between items-center">
                <h4 className="font-semibold text-gray-900">Position Reference List</h4>
                <button
                  onClick={() => setShowAddPositionModal(!showAddPositionModal)}
                  className="flex items-center gap-1 px-3 py-1 text-sm text-blue-600 hover:bg-blue-100 rounded">
                  <Plus className="h-4 w-4" />
                  Add Position
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {positions.map((pos) => (
                  <div key={pos.id} className="flex items-center justify-between bg-white p-2 rounded border border-gray-200">
                    <span className="text-sm text-gray-700">{pos.name}</span>
                    <button
                      onClick={() => handleDeletePosition(pos.id)}
                      className="text-red-600 hover:text-red-700 p-1">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Add Position Form */}
              {showAddPositionModal && (
                <div className="bg-white p-3 rounded border border-blue-300 space-y-2">
                  <input
                    type="text"
                    value={newPositionName}
                    onChange={(e) => setNewPositionName(e.target.value)}
                    placeholder="Enter new position name"
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:border-bx-orange"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setShowAddPositionModal(false)}
                      className="px-3 py-1 text-xs text-gray-700 border border-gray-300 rounded hover:bg-gray-50">
                      Cancel
                    </button>
                    <button
                      onClick={handleAddPosition}
                      className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-60"
                      disabled={!newPositionName.trim()}>
                      Add
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="space-y-2">
            {orgNodes.length > 0 ? (
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="text-sm text-gray-600 mb-4">Organizational Structure</div>
                {orgNodes
                  .filter(node => !node.reportsTo)
                  .map((node) => (
                    <div key={node.id} className="space-y-2">
                      <div className="border-l-4 border-bx-orange pl-4 py-2">
                        <div className="flex items-center justify-between bg-white p-3 rounded border border-gray-200 hover:bg-gray-50">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-bold text-gray-900">{node.employeeName}</h4>
                              <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">
                                {getPositionName(node.position)}
                              </span>
                            </div>
                            <div className="flex gap-3 text-xs text-gray-500 mt-1">
                              {node.businessUnit && <span>🏢 {getBusinessUnitName(node.businessUnit)}</span>}
                              {node.location && <span>📍 {node.location}</span>}
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => handleEditOrgNode(node)} className="p-2 text-blue-600 hover:bg-blue-50 rounded"><Edit2 className="h-4 w-4" /></button>
                            <button onClick={() => handleDeleteOrgNode(node.id)} className="p-2 text-red-600 hover:bg-red-50 rounded"><Trash2 className="h-4 w-4" /></button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>No organizational nodes created yet. Click "Add Org Node" to add people to the organizational hierarchy.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Add Org Node Modal */}
      {showAddOrgNodeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Add Organizational Node</h3>
              <button onClick={() => setShowAddOrgNodeModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <form onSubmit={handleAddOrgNode} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Employee Name *</label>
                <input
                  type="text"
                  value={newOrgNodeEmployeeName}
                  onChange={(e) => setNewOrgNodeEmployeeName(e.target.value)}
                  placeholder="e.g., John Smith"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Position *</label>
                <select
                  value={newOrgNodePosition}
                  onChange={(e) => setNewOrgNodePosition(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  required
                >
                  <option value="">Select a position</option>
                  {positions.map((pos) => (
                    <option key={pos.id} value={pos.id}>
                      {pos.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reports To (Optional)</label>
                <select
                  value={newOrgNodeReportsTo}
                  onChange={(e) => setNewOrgNodeReportsTo(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">CEO / Top Level</option>
                  {orgNodes.map((node) => (
                    <option key={node.id} value={node.id}>
                      {node.employeeName} ({getPositionName(node.position)})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit (Optional)</label>
                <select
                  value={newOrgNodeBusinessUnit}
                  onChange={(e) => setNewOrgNodeBusinessUnit(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select Business Unit</option>
                  {businessUnits.map((bu) => (
                    <option key={bu.id} value={bu.id}>
                      {bu.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Location (Optional)</label>
                <input
                  type="text"
                  value={newOrgNodeLocation}
                  onChange={(e) => setNewOrgNodeLocation(e.target.value)}
                  placeholder="e.g., Austin, TX"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddOrgNodeModal(false)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                  disabled={isSubmittingOrgNode || !newOrgNodeEmployeeName.trim() || !newOrgNodePosition.trim()}
                >
                  {isSubmittingOrgNode ? "Adding..." : "Add Node"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Org Node Modal */}
      {editingOrgNodeId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Edit Organizational Node</h3>
              <button onClick={() => setEditingOrgNodeId(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveEditedOrgNode(); }} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Employee Name *</label>
                <input
                  type="text"
                  value={editOrgNodeEmployeeName}
                  onChange={(e) => setEditOrgNodeEmployeeName(e.target.value)}
                  placeholder="e.g., John Smith"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Position *</label>
                <select
                  value={editOrgNodePosition}
                  onChange={(e) => setEditOrgNodePosition(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                  required
                >
                  <option value="">Select a position</option>
                  {positions.map((pos) => (
                    <option key={pos.id} value={pos.id}>
                      {pos.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reports To (Optional)</label>
                <select
                  value={editOrgNodeReportsTo}
                  onChange={(e) => setEditOrgNodeReportsTo(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">CEO / Top Level</option>
                  {orgNodes.filter(n => n.id !== editingOrgNodeId).map((node) => (
                    <option key={node.id} value={node.id}>
                      {node.employeeName} ({getPositionName(node.position)})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Unit (Optional)</label>
                <select
                  value={editOrgNodeBusinessUnit}
                  onChange={(e) => setEditOrgNodeBusinessUnit(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                >
                  <option value="">Select Business Unit</option>
                  {businessUnits.map((bu) => (
                    <option key={bu.id} value={bu.id}>
                      {bu.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Location (Optional)</label>
                <input
                  type="text"
                  value={editOrgNodeLocation}
                  onChange={(e) => setEditOrgNodeLocation(e.target.value)}
                  placeholder="e.g., Austin, TX"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-bx-orange"
                />
              </div>
              <div className="flex gap-2 justify-end pt-4">
                <button
                  type="button"
                  onClick={() => setEditingOrgNodeId(null)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-bx-orange text-white rounded-lg hover:bg-bx-orange-hover disabled:opacity-60"
                  disabled={!editOrgNodeEmployeeName.trim() || !editOrgNodePosition.trim()}
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
