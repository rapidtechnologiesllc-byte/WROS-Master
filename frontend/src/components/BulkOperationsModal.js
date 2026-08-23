// DEFECT-12: Bulk Operations Framework
import { useState } from "react";
import { AlertCircle, CheckCircle2, Loader } from "lucide-react";
import { Button } from "./ui";

export function BulkOperationsBar({ selectedCount, actions, onAction }) {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 border-t border-gray-200 bg-white shadow-lg p-4 z-40">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        <div className="text-sm font-semibold text-gray-900">
          {selectedCount} selected
        </div>

        <div className="flex gap-2">
          {actions.map((action) => (
            <Button
              key={action.id}
              variant={action.variant || "secondary"}
              size="sm"
              onClick={() => onAction(action.id)}
            >
              {action.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function BulkOperationProgress({ isOpen, operation, progress, onClose }) {
  if (!isOpen) return null;

  const percentage = (progress.completed / progress.total) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="rounded-lg bg-white shadow-lg p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">
          {operation?.label || "Processing"}
        </h3>

        <div className="mb-4">
          <div className="text-sm text-gray-600 mb-2">
            {progress.completed} of {progress.total}
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>

        {progress.currentItem && (
          <div className="mb-4 text-xs text-gray-600">
            Processing: {progress.currentItem}
          </div>
        )}

        {progress.completed === progress.total && (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 mb-4 flex gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-emerald-900">Complete</div>
              <div className="text-sm text-emerald-700">
                {progress.completed} items processed
              </div>
            </div>
          </div>
        )}

        {progress.errors > 0 && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 mb-4 flex gap-2">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-amber-900">Errors</div>
              <div className="text-sm text-amber-700">
                {progress.errors} items failed
              </div>
            </div>
          </div>
        )}

        <Button
          variant="primary"
          onClick={onClose}
          disabled={progress.completed < progress.total}
          className="w-full"
        >
          {progress.completed < progress.total ? (
            <>
              <Loader className="h-4 w-4 animate-spin mr-2" />
              Processing...
            </>
          ) : (
            "Close"
          )}
        </Button>
      </div>
    </div>
  );
}

export function useBulkOperations() {
  const [selected, setSelected] = useState(new Set());
  const [progress, setProgress] = useState(null);

  const selectAll = (items) => {
    setSelected(new Set(items.map((i) => i.id)));
  };

  const deselectAll = () => {
    setSelected(new Set());
  };

  const toggleItem = (id) => {
    const newSelected = new Set(selected);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelected(newSelected);
  };

  const startOperation = () => {
    setProgress({
      total: selected.size,
      completed: 0,
      errors: 0,
      currentItem: null,
    });
  };

  const updateProgress = (completed, currentItem, hasError = false) => {
    setProgress((p) => ({
      ...p,
      completed,
      currentItem,
      errors: p.errors + (hasError ? 1 : 0),
    }));
  };

  return {
    selected,
    progress,
    selectAll,
    deselectAll,
    toggleItem,
    startOperation,
    updateProgress,
  };
}
