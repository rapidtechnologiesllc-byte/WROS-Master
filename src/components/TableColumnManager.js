// DEFECT-3: Reusable Table Column Manager
// Allows show/hide/reorder columns, sort by headers
// Persists to localStorage

import { useState, useEffect } from "react";
import { Settings2, ChevronUp, ChevronDown } from "lucide-react";
import { Button } from "./ui";

export function useTableColumns(tableKey, defaultColumns) {
  const [columns, setColumns] = useState(() => {
    const saved = localStorage.getItem(`table_columns_${tableKey}`);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return defaultColumns;
      }
    }
    return defaultColumns;
  });

  const [sortBy, setSortBy] = useState(() => {
    const saved = localStorage.getItem(`table_sort_${tableKey}`);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return { column: null, direction: "asc" };
      }
    }
    return { column: null, direction: "asc" };
  });

  const saveColumns = (newColumns) => {
    setColumns(newColumns);
    localStorage.setItem(`table_columns_${tableKey}`, JSON.stringify(newColumns));
  };

  const saveSort = (column) => {
    const direction = sortBy.column === column && sortBy.direction === "asc" ? "desc" : "asc";
    const newSort = { column, direction };
    setSortBy(newSort);
    localStorage.setItem(`table_sort_${tableKey}`, JSON.stringify(newSort));
  };

  const updateColumnVisibility = (columnKey, visible) => {
    const updated = columns.map((col) =>
      col.key === columnKey ? { ...col, visible } : col
    );
    saveColumns(updated);
  };

  const reorderColumns = (fromIndex, toIndex) => {
    const updated = [...columns];
    const [removed] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, removed);
    saveColumns(updated);
  };

  const getVisibleColumns = () => columns.filter((col) => col.visible !== false);

  const getSortedData = (data) => {
    if (!sortBy.column || !data) return data;
    const sorted = [...data].sort((a, b) => {
      const aVal = a[sortBy.column] || "";
      const bVal = b[sortBy.column] || "";
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortBy.direction === "asc" ? cmp : -cmp;
    });
    return sorted;
  };

  return {
    columns,
    sortBy,
    visibleColumns: getVisibleColumns(),
    updateColumnVisibility,
    reorderColumns,
    saveSort,
    getSortedData,
  };
}

export function ColumnSettingsModal({ columns, onUpdate, onClose }) {
  const [cols, setCols] = useState(columns);

  const handleToggle = (key) => {
    setCols(cols.map((col) => (col.key === key ? { ...col, visible: !col.visible } : col)));
  };

  const handleReorder = (fromIndex, toIndex) => {
    const updated = [...cols];
    const [removed] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, removed);
    setCols(updated);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="rounded-lg bg-white p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Column Settings</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            ✕
          </button>
        </div>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {cols.map((col, idx) => (
            <div key={col.key} className="flex items-center gap-2 p-2 border rounded">
              <input
                type="checkbox"
                checked={col.visible !== false}
                onChange={() => handleToggle(col.key)}
                className="cursor-pointer"
              />
              <span className="flex-1 text-sm font-medium">{col.label}</span>
              <div className="flex gap-1">
                <button
                  onClick={() => idx > 0 && handleReorder(idx, idx - 1)}
                  disabled={idx === 0}
                  className="p-1 hover:bg-gray-100 disabled:opacity-50"
                  title="Move up"
                >
                  ↑
                </button>
                <button
                  onClick={() => idx < cols.length - 1 && handleReorder(idx, idx + 1)}
                  disabled={idx === cols.length - 1}
                  className="p-1 hover:bg-gray-100 disabled:opacity-50"
                  title="Move down"
                >
                  ↓
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => onUpdate(cols)}
            className="flex-1 bg-blue-600 text-white rounded px-3 py-2 font-medium hover:bg-blue-700"
          >
            Save
          </button>
          <button
            onClick={onClose}
            className="flex-1 border rounded px-3 py-2 font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export function TableColumnSettingsButton({ onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="p-2 hover:bg-gray-100 rounded-lg border border-gray-300"
      title="Column settings"
    >
      <Settings2 className="h-4 w-4" />
    </button>
  );
}

export function SortableTableHeader({ label, columnKey, currentSort, onSort, sortable = true }) {
  const isActive = currentSort.column === columnKey;
  const isSortable = sortable !== false;

  return (
    <th
      onClick={() => isSortable && onSort(columnKey)}
      className={isSortable ? "cursor-pointer hover:bg-gray-100" : ""}
    >
      <div className="flex items-center gap-1 font-semibold">
        {label}
        {isSortable && (
          <span className="text-gray-400">
            {isActive && currentSort.direction === "asc" ? (
              <ChevronUp className="h-4 w-4 text-blue-600" />
            ) : isActive && currentSort.direction === "desc" ? (
              <ChevronDown className="h-4 w-4 text-blue-600" />
            ) : (
              <span className="text-xs">↕</span>
            )}
          </span>
        )}
      </div>
    </th>
  );
}
