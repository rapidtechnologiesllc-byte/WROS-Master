import React from 'react';
import './PermissionValidation.css';

const PermissionValidation = ({ validation }) => {
  if (!validation) {
    return <div className="validation-empty">No validation data</div>;
  }

  const { valid, redundant_permissions = [], conflicts = [], warnings = [] } = validation;

  return (
    <div className="permission-validation">
      {/* Status */}
      <div className={`validation-status ${valid ? 'valid' : 'invalid'}`}>
        <span className="status-icon">{valid ? '✅' : '⚠️'}</span>
        <span className="status-text">{valid ? 'Permissions are valid' : 'Conflicts detected'}</span>
      </div>

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <div className="validation-section conflicts">
          <h4>🚫 Conflicts ({conflicts.length})</h4>
          <ul className="conflicts-list">
            {conflicts.map((conflict, idx) => (
              <li key={idx} className="conflict-item">
                <strong>{conflict.conflict}</strong> conflicts with <strong>{conflict.with}</strong>
              </li>
            ))}
          </ul>
          <p className="section-help">These permissions cannot coexist and should be reviewed</p>
        </div>
      )}

      {/* Redundant Permissions */}
      {redundant_permissions.length > 0 && (
        <div className="validation-section redundant">
          <h4>♻️ Redundant Permissions ({redundant_permissions.length})</h4>
          <ul className="redundant-list">
            {redundant_permissions.map((item, idx) => (
              <li key={idx} className="redundant-item">
                <code>{item.permission}</code> is implied by <code>{item.implied_by}</code>
                <button className="btn-remove" title="Remove redundant permission">
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <p className="section-help">
            These permissions are automatically granted by other permissions
          </p>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="validation-section warnings">
          <h4>⚠️ Warnings ({warnings.length})</h4>
          <ul className="warnings-list">
            {warnings.map((warning, idx) => (
              <li key={idx} className="warning-item">
                {warning}
              </li>
            ))}
          </ul>
          <p className="section-help">These are best practice recommendations</p>
        </div>
      )}

      {/* All Good */}
      {valid && conflicts.length === 0 && redundant_permissions.length === 0 && warnings.length === 0 && (
        <div className="validation-success">
          <div className="success-icon">🎉</div>
          <h4>Perfect!</h4>
          <p>No conflicts or issues detected. This role template is well-configured.</p>
        </div>
      )}
    </div>
  );
};

export default PermissionValidation;
