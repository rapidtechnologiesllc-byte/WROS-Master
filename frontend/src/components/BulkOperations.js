// DEFECT-12: Bulk operations framework for multi-select actions
// Select All, bulk actions, progress bar, confirmation modal

import { useState } from "react";
import { Check, X, Trash2, ArrowRight } from "lucide-react";
import { Button, Card } from "./ui";

export function useBulkSelection(items = []) {
  const [selectedIds, setSelectedIds] = useState(new Set());

  const selectAll = (shouldSelect = true) => {
    if (shouldSelect) {
      setSelectedIds(new Set(items.map((item) => item.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const toggleItem = (id) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedIds(newSet);
  };

  const isAllSelected = items.length > 0 && selectedIds.size === items.length;
  const selectedCount = selectedIds.size;

  return {
    selectedIds,
    selectAll,
    toggleItem,
    isAllSelected,
    selectedCount,
    clearSelection: () => setSelectedIds(new Set()),
  };
}

export function BulkOperationsBar({ selectedCount, operations, onSelectAll, isAllSelected }) {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-blue-600 text-white p-4">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="font-semibold">{selectedCount} selected</span>
          <button
            onClick={() => onSelectAll(!isAllSelected)}
            className="text-sm underline hover:opacity-80"
          >
            {isAllSelected ? "Deselect All" : "Select All"}
          </button>
        </div>
        <div className="flex gap-2">
          {operations.map((op) => (
            <Button
              key={op.id}
              variant={op.variant || "secondary"}
              size="sm"
              onClick={op.onConfirm}
              disabled={op.disabled}
            >
              {op.icon && <op.icon className="h-4 w-4 mr-1" />}
              {op.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function BulkConfirmationModal({ action, count, onConfirm, onCancel }) {
  if (!action) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-2">{action.title}</h2>
        <p className="text-gray-600 text-sm mb-4">
          This will {action.description} {count} item{count !== 1 ? "s" : ""}. This cannot be undone.
        </p>

        <div className="flex gap-2">
          <Button variant="danger" onClick={() => onConfirm(action.id)} className="flex-1">
            <action.icon className="h-4 w-4 mr-2" />
            {action.confirmLabel || "Confirm"}
          </Button>
          <Button variant="ghost" onClick={onCancel} className="flex-1">
            Cancel
          </Button>
        </div>
      </Card>
    </div>
  );
}

export function BulkProgressModal({ operation, progress, itemsProcessed, totalItems }) {
  const percent = Math.round((itemsProcessed / totalItems) * 100);
  const isComplete = itemsProcessed === totalItems;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">{operation}</h2>

        {!isComplete && (
          <>
            <div className="mb-4 text-sm text-gray-600">
              Processing {itemsProcessed} of {totalItems} items...
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${percent}%` }}
              />
            </div>
            <div className="text-center text-sm font-semibold text-gray-700">{percent}%</div>
          </>
        )}

        {isComplete && (
          <div className="text-center">
            <Check className="h-12 w-12 text-green-600 mx-auto mb-3" />
            <p className="font-semibold text-green-900">✓ Complete!</p>
            <p className="text-sm text-gray-600 mt-1">
              Successfully processed all {totalItems} items.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

// Example operations for common bulk actions
export const BULK_OPERATIONS = {
  DELETE: {
    id: "delete",
    label: "Delete",
    title: "Delete Items",
    description: "delete",
    confirmLabel: "Delete All",
    icon: Trash2,
    variant: "danger",
  },
  REASSIGN: {
    id: "reassign",
    label: "Reassign",
    title: "Reassign Items",
    description: "reassign",
    confirmLabel: "Reassign",
    icon: ArrowRight,
    variant: "secondary",
  },
};
