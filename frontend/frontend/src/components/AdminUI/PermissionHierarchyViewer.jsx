import React, { useState, useEffect } from 'react';
import { roleTemplatesAPI } from '../../services/api/roleTemplates';
import './PermissionHierarchyViewer.css';

const PermissionHierarchyViewer = ({ templateId }) => {
  const [tree, setTree] = useState(null);
  const [expandedResources, setExpandedResources] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadPermissionTree();
  }, [templateId]);

  const loadPermissionTree = async () => {
    try {
      setLoading(true);
      const response = await roleTemplatesAPI.getPermissionTree(templateId);
      setTree(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load permission hierarchy');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleResource = (resource) => {
    setExpandedResources((prev) => ({
      ...prev,
      [resource]: !prev[resource],
    }));
  };

  if (loading) {
    return <div className="loading">Loading permission hierarchy...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (!tree) {
    return <div className="empty">No permission tree available</div>;
  }

  const { direct_permissions = [], implied_permissions = [], by_resource = {} } = tree;

  return (
    <div className="permission-hierarchy">
      <div className="hierarchy-summary">
        <div className="summary-item">
          <span className="count">{direct_permissions.length}</span>
          <span className="label">Direct Permissions</span>
        </div>
        <div className="summary-item">
          <span className="count">{implied_permissions.length}</span>
          <span className="label">Implied Permissions</span>
        </div>
        <div className="summary-item">
          <span className="count">{tree.total_permissions}</span>
          <span className="label">Total Permissions</span>
        </div>
      </div>

      {/* By Resource Tree */}
      <div className="hierarchy-tree">
        <h4>Permissions by Resource</h4>

        {Object.entries(by_resource).length === 0 ? (
          <p className="empty-tree">No permissions assigned</p>
        ) : (
          <div className="resource-tree">
            {Object.entries(by_resource).map(([resource, actions]) => (
              <div key={resource} className="resource-node">
                <button
                  className="resource-toggle"
                  onClick={() => toggleResource(resource)}
                >
                  <span className="toggle-icon">{expandedResources[resource] ? '▼' : '▶'}</span>
                  <span className="resource-name">{resource}</span>
                  <span className="action-count">({actions.length})</span>
                </button>

                {expandedResources[resource] && (
                  <div className="action-list">
                    {actions.map((action, idx) => (
                      <div key={idx} className={`action-item action-${action}`}>
                        <span className="action-icon">
                          {action === 'view' && '👁️'}
                          {action === 'create' && '➕'}
                          {action === 'edit' && '✏️'}
                          {action === 'delete' && '🗑️'}
                        </span>
                        <span className="action-name">{action}</span>
                        {implied_permissions.includes(`${resource}.${action}`) && (
                          <span className="implied-badge" title="This permission is implied by another">
                            (Implied)
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Direct vs Implied */}
      <div className="hierarchy-breakdown">
        <div className="breakdown-section">
          <h4>🎯 Direct Permissions ({direct_permissions.length})</h4>
          {direct_permissions.length === 0 ? (
            <p>None</p>
          ) : (
            <div className="permission-list">
              {direct_permissions.map((perm, idx) => (
                <span key={idx} className="permission-tag direct">
                  {perm}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="breakdown-section">
          <h4>🔗 Implied Permissions ({implied_permissions.length})</h4>
          {implied_permissions.length === 0 ? (
            <p>None</p>
          ) : (
            <div className="permission-list">
              {implied_permissions.map((perm, idx) => (
                <span key={idx} className="permission-tag implied">
                  {perm}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="hierarchy-legend">
        <div className="legend-item">
          <span className="legend-tag direct">Direct</span>
          <span>Explicitly assigned</span>
        </div>
        <div className="legend-item">
          <span className="legend-tag implied">Implied</span>
          <span>Granted by hierarchy rules</span>
        </div>
      </div>
    </div>
  );
};

export default PermissionHierarchyViewer;
