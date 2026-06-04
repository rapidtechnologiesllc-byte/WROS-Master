import React, { useRef, useState } from "react";
import SignatureCanvas from "react-signature-canvas";
import { toast } from "react-toastify";

const SignatureModal = ({ isOpen, onClose, onSave }) => {
  const sigCanvas = useRef(null);
  const [signatureType, setSignatureType] = useState("draw");
  const [typedSignature, setTypedSignature] = useState("");

  if (!isOpen) return null;

  const clearSignature = () => {
    sigCanvas.current?.clear();
    setTypedSignature("");
  };

  const handleSave = async () => {
    let pngData = "";
    if (signatureType === "draw") {
      if (sigCanvas.current?.isEmpty()) {
        toast.error("Please provide signature");
        return;
      }
      const canvas = sigCanvas.current.getCanvas();
      canvas.toBlob((blob) => {
        const file = new File([blob], "signature.png", {
          type: "image/png",
        });

        onSave(file);
      }, "image/png");

      return;
    }
    if (signatureType === "type") {
      if (!typedSignature.trim()) {
        toast.error("Please enter signature");
        return;
      }
      const canvas = document.createElement("canvas");
      canvas.width = 500;
      canvas.height = 150;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "black";
      ctx.font = "48px cursive";
      ctx.fillText(typedSignature, 20, 90);
      pngData = canvas.toDataURL("image/png");
    }

    onSave(pngData);
  };

  return (
    <div className="fixed inset-0 z-[9999] bg-black/50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg w-[650px] shadow-xl">
        <h2 className="text-xl font-semibold mb-4">Add Signature</h2>
        <div className="flex gap-4 mb-4">
          <button onClick={() => setSignatureType("draw")}>Draw</button>
          <button onClick={() => setSignatureType("type")}>Type</button>
        </div>

        {signatureType === "draw" ? (
          <SignatureCanvas
            ref={sigCanvas}
            penColor="black"
            canvasProps={{
              width: 600,
              height: 250,
              className: "border border-gray-300 rounded bg-white",
            }}
          />
        ) : (
          <input
            value={typedSignature}
            onChange={(e) => setTypedSignature(e.target.value)}
            placeholder="Type your signature"
            className="border p-3 w-full"
          />
        )}
        <div className="flex justify-end gap-3 mt-4">
          <button onClick={clearSignature}>Clear</button>
          <button onClick={onClose}>Cancel</button>
          <button
            onClick={handleSave}
            className="bg-blue-500 text-white px-4 py-2 rounded"
          >
            Save Signature
          </button>
        </div>
      </div>
    </div>
  );
};

export default SignatureModal;
