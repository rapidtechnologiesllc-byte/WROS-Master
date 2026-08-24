import React from "react";
import { AlertCircle, X } from "lucide-react";

export default function ScreenErrorDisplay({ error, onDismiss }) {
  if (!error) return null;

  return (
    <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-4 flex items-start gap-3">
      <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
      <div className="flex-1">
        <p className="text-sm font-medium text-red-900">{error}</p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-red-400 hover:text-red-600 flex-shrink-0"
        >
          <X className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
