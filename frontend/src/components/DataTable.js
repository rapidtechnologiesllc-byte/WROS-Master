// DEFECT-3: Reusable DataTable with column customization and sorting
import { useState } from "react";
import { useTableColumns, ColumnSettingsModal, SortableTableHeader, TableColumnSettingsButton } from "./TableColumnManager";

export function DataTable({
  tableKey,
  defaultColumns,
  data,
  renderRow,
  loading,
  onRowClick,
  title,
  subtitle
}) {
  const {
    columns,
    sortBy,
    visibleColumns,
    updateColumnVisibility,
    reorderColumns,
    saveSort,
    getSortedData,
  } = useTableColumns(tableKey, defaultColumns);

  const [showColumnSettings, setShowColumnSettings] = useState(false);

  const handleSaveColumns = (newColumns) => {
    newColumns.forEach((col, idx) => {
      const oldIndex = columns.findIndex((c) => c.key === col.key);
      if (oldIndex !== idx) {
        reorderColumns(oldIndex, idx);
      }
    });
    newColumns.forEach((col) => {
      if (col.visible !== undefined) {
        updateColumnVisibility(col.key, col.visible);
      }
    });
    setShowColumnSettings(false);
  };

  const sortedData = getSortedData(data);

  return (
    <div className="space-y-3">
      {title && (
        <div className="flex items-center justify-between">
          <div>
            {title && <h2 className="text-lg font-semibold">{title}</h2>}
            {subtitle && <p className="text-sm text-gray-600">{subtitle}</p>}
          </div>
          <TableColumnSettingsButton onOpen={() => setShowColumnSettings(true)} />
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              {visibleColumns.map((col) => (
                <th key={col.key} className="px-4 py-2 text-left">
                  <SortableTableHeader
                    label={col.label}
                    columnKey={col.key}
                    currentSort={sortBy}
                    onSort={saveSort}
                    sortable={col.sortable !== false}
                  />
                </th>
              ))}
              {renderRow && <th className="px-4 py-2 text-left">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={visibleColumns.length + 1} className="px-4 py-8 text-center text-gray-500">
                  Loading...
                </td>
              </tr>
            ) : sortedData && sortedData.length > 0 ? (
              sortedData.map((row, idx) => renderRow ? renderRow(row, visibleColumns, idx) : null)
            ) : (
              <tr>
                <td colSpan={visibleColumns.length + 1} className="px-4 py-8 text-center text-gray-500">
                  No data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showColumnSettings && (
        <ColumnSettingsModal
          columns={columns}
          onUpdate={handleSaveColumns}
          onClose={() => setShowColumnSettings(false)}
        />
      )}
    </div>
  );
}
