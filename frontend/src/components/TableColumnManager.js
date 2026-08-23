// DEFECT-3: Table Column Customization & Sorting
import { useEffect, useState } from "react";
import { Settings2, Eye, EyeOff, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "./ui";

export function useTableColumns(tableName, defaultColumns) {
  const [columns, setColumns] = useState(defaultColumns);
  const [sortBy, setSortBy] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  // Load saved preferences from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(`table_columns_${tableName}`);
    if (saved) {
      const { columns: savedCols, sort } = JSON.parse(saved);
      setColumns(savedCols);
      if (sort) {
        setSortBy(sort.column);
        setSortDir(sort.direction);
      }
    }
  }, [tableName]);

  // Save preferences
  const savePreferences = (cols, sort) => {
    localStorage.setItem(
      `table_columns_${tableName}`,
      JSON.stringify({ columns: cols, sort })
    );
  };

  const toggleColumn = (key) => {
    const updated = columns.map((c) =>
      c.key === key ? { ...c, visible: !c.visible } : c
    );
    setColumns(updated);
    savePreferences(updated, sortBy ? { column: sortBy, direction: sortDir } : null);
  };

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortDir("asc");
    }
    savePreferences(columns, { column: key, direction: sortDir === "asc" ? "desc" : "asc" });
  };

  return {
    columns: columns.filter((c) => c.visible),
    allColumns: columns,
    toggleColumn,
    handleSort,
    sortBy,
    sortDir,
  };
}

export function TableColumnSettings({ columns, onToggle }) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowMenu(!showMenu)}
      >
        <Settings2 className="h-4 w-4" />
      </Button>

      {showMenu && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-lg border bg-white shadow-lg p-3 z-50">
          <div className="text-sm font-semibold mb-3">Show/Hide Columns</div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {columns.map((col) => (
              <label key={col.key} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={col.visible !== false}
                  onChange={() => onToggle(col.key)}
                  className="rounded"
                />
                <span className="text-sm">{col.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function SortableHeader({ label, sortable, active, direction, onSort }) {
  if (!sortable) return <>{label}</>;

  return (
    <button
      onClick={onSort}
      className="flex items-center gap-1 font-semibold hover:text-blue-600"
    >
      {label}
      {active && (
        direction === "asc" ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      )}
    </button>
  );
}
