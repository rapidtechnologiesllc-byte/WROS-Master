import React, { useState } from 'react';
import './RoleTemplateList.css';

const RoleTemplateList = ({ templates, selectedId, onSelect, onDelete, loading }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSystemOnly, setFilterSystemOnly] = useState(false);

  const filteredTemplates = templates.filter((template) => {
    const matchesSearch =
      template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      template.display_name.toLowerCase().includes(searchTerm.toLowerCase());

    if (filterSystemOnly) {
      return matchesSearch && template.is_system;
    }

    return matchesSearch;
  });

  return (
    <div className="role-template-list">
      <div className="list-header">
        <h3>Templates</h3>
        <span className="count">{filteredTemplates.length}</span>
      </div>

      {/* Search */}
      <div className="list-search">
        <input
          type="text"
          placeholder="Search templates..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      {/* Filters */}
      <div className="list-filters">
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filterSystemOnly}
            onChange={(e) => setFilterSystemOnly(e.target.checked)}
          />
          <span>System Only</span>
        </label>
      </div>

      {/* Template List */}
      <div className="templates-scroll">
        {loading ? (
          <div className="loading">Loading templates...</div>
        ) : filteredTemplates.length === 0 ? (
          <div className="empty-list">
            <p>No templates found</p>
          </div>
        ) : (
          <ul className="templates-list">
            {filteredTemplates.map((template) => (
              <li key={template.id} className={selectedId === template.id ? 'active' : ''}>
                <button
                  className="template-item"
                  onClick={() => onSelect(template)}
                  title={template.description}
                >
                  <div className="template-header">
                    <span className="template-name">{template.display_name || template.name}</span>
                    {template.is_system && <span className="system-badge">System</span>}
                  </div>
                  <div className="template-meta">
                    <span className="permission-count">
                      {template.permissions?.length || 0} permissions
                    </span>
                  </div>
                </button>

                {selectedId === template.id && !template.is_system && (
                  <div className="template-actions">
                    <button
                      className="btn-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(template.id);
                      }}
                      title="Delete template"
                    >
                      🗑️
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default RoleTemplateList;
