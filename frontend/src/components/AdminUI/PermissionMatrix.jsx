import React, { useState, useEffect } from 'react';
import './PermissionMatrix.css';

const PermissionMatrix = ({ template, loading }) => {
  const [permissions, setPermissions] = useState([]);
  const [resourcesMap, setResourcesMap] = useState({});

  useEffect(() => {
    if (template?.permissions) {
      // Group by resource
      const grouped = {};
      const resources = {};

      template.permissions.forEach((perm) => {
        const resourceId = perm.resource_id;
        const resourceName = perm.resource_name || `Resource ${resourceId}`;

        resources[resourceId] = {
          id: resourceId,
          name: resourceName,
          display_name: perm.resource_display || resourceName,
        };

        if (!grouped[resourceId]) {
          grouped[resourceId] = {
            view: false,
            create: false,
            edit: false,
            delete: false,
          };
        }

        grouped[resourceId] = {
          view: grouped[resourceId].view || perm.can_view,
          create: grouped[resourceId].create || perm.can_create,
          edit: grouped[resourceId].edit || perm.can_edit,
          delete: grouped[resourceId].delete || perm.can_delete,
        };
      });

      setResourcesMap(resources);

      // Convert to array sorted by resource name
      const sortedPerms = Object.entries(grouped).map(([resourceId, actions]) => ({
        resourceId: parseInt(resourceId),
        resourceName: resources[resourceId]?.display_name || `Resource ${resourceId}`,
        ...actions,
      }));

      setPermissions(sortedPerms.sort((a, b) => a.resourceName.localeCompare(b.resourceName)));
    }
  }, [template]);

  if (loading) {
    return <div className="loading">Loading permissions...</div>;
  }

  if (!permissions.length) {
    return (
      <div className="empty-matrix">
        <p>No permissions assigned to this template</p>
      </div>
    );
  }

  // Count permissions by action
  const actionCounts = {
    view: permissions.filter((p) => p.view).length,
    create: permissions.filter((p) => p.create).length,
    edit: permissions.filter((p) => p.edit).length,
    delete: permissions.filter((p) => p.delete).length,
  };

  return (
    <div className="permission-matrix">
      {/* Summary */}
      <div className="matrix-summary">
        <div className="summary-card">
          <span className="count">{permissions.length}</span>
          <span className="label">Resources</span>
        </div>
        <div className="summary-card">
          <span className="count">{actionCounts.view}</span>
          <span className="label">View Access</span>
        </div>
        <div className="summary-card">
          <span className="count">{actionCounts.create}</span>
          <span className="label">Create Access</span>
        </div>
        <div className="summary-card">
          <span className="count">{actionCounts.edit}</span>
          <span className="label">Edit Access</span>
        </div>
        <div className="summary-card">
          <span className="count">{actionCounts.delete}</span>
          <span className="label">Delete Access</span>
        </div>
      </div>

      {/* Table */}
      <div className="matrix-table-wrapper">
        <table className="matrix-table">
          <thead>
            <tr>
              <th>Resource</th>
              <th>
                <span className="action-icon">👁️</span>
                <span className="action-label">View</span>
              </th>
              <th>
                <span className="action-icon">➕</span>
                <span className="action-label">Create</span>
              </th>
              <th>
                <span className="action-icon">✏️</span>
                <span className="action-label">Edit</span>
              </th>
              <th>
                <span className="action-icon">🗑️</span>
                <span className="action-label">Delete</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {permissions.map((perm, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? 'even' : 'odd'}>
                <td className="resource-cell">{perm.resourceName}</td>
                <td className="action-cell">{perm.view ? '✓' : '—'}</td>
                <td className="action-cell">{perm.create ? '✓' : '—'}</td>
                <td className="action-cell">{perm.edit ? '✓' : '—'}</td>
                <td className="action-cell">{perm.delete ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="matrix-legend">
        <div className="legend-item">
          <span className="legend-check">✓</span>
          <span>Permission Granted</span>
        </div>
        <div className="legend-item">
          <span className="legend-dash">—</span>
          <span>Permission Denied</span>
        </div>
      </div>
    </div>
  );
};

export default PermissionMatrix;
