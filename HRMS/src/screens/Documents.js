// Document upload checklist placeholder screen.
import { useState } from "react";
import { FileText } from "lucide-react";
import { Button, Card } from "../components/ui";

export default function Documents({ candidate, onSubmit }) {
  const [docs, setDocs] = useState({
    idProof: false,
    addressProof: false,
    education: false
  });

  const all = Object.values(docs).every(Boolean);

  return (
    <div className="grid gap-4">
      <Card title="Candidate Uploads Documents" icon={<FileText className="h-4 w-4" />}>
        <div className="mb-3 text-sm text-gray-700">
          Candidate: <span className="font-semibold">{candidate.name}</span>
        </div>

        <div className="space-y-2">
          {[
            ["ID Proof", "idProof"],
            ["Address Proof", "addressProof"],
            ["Education Documents", "education"]
          ].map(([label, key]) => (
            <label
              key={key}
              className="flex items-center justify-between rounded-2xl border bg-white p-4"
            >
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4" />
                <div className="text-sm font-semibold">{label}</div>
              </div>
              <input
                type="checkbox"
                checked={docs[key]}
                onChange={(e) => setDocs((d) => ({ ...d, [key]: e.target.checked }))}
                className="h-5 w-5"
              />
            </label>
          ))}
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={onSubmit} disabled={!all}>
            Submit for verification
          </Button>
        </div>

        {!all ? (
          <div className="mt-2 text-xs text-gray-500">
            Select all documents to enable submit (demo behavior).
          </div>
        ) : null}
      </Card>
    </div>
  );
}
