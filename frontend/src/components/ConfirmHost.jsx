import React, { useEffect, useState } from 'react';
import { registerDialogHost } from '../utils/dialogs';

// The one place confirmations and notices render (mounted once in App). Native
// window.confirm / alert are not used: embedded browsers suppress them (confirm returns
// false at once), which silently disabled every delete button.
export default function ConfirmHost() {
  const [dialog, setDialog] = useState(null); // { kind, message, confirmLabel, danger, resolve }

  useEffect(() => registerDialogHost(setDialog), []);

  if (!dialog) return null;
  const close = (result) => {
    dialog.resolve(result);
    setDialog(null);
  };
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <p className="whitespace-pre-line text-sm text-gray-800">{dialog.message}</p>
        <div className="mt-6 flex justify-end gap-2">
          {dialog.kind === 'confirm' && (
            <button
              type="button"
              onClick={() => close(false)}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            autoFocus
            onClick={() => close(true)}
            className={`rounded-lg px-4 py-2 text-sm text-white ${dialog.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-bx-orange hover:bg-bx-orange-hover'}`}
          >
            {dialog.kind === 'confirm' ? dialog.confirmLabel : 'OK'}
          </button>
        </div>
      </div>
    </div>
  );
}
