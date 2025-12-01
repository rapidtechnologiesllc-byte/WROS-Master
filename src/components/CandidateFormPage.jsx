// src/components/CandidateFormPage.jsx
import React, { useEffect, useState } from "react";

export default function CandidateFormPage({ currentUser }) {
  const [joiningDate, setJoiningDate] = useState("");
  const [position, setPosition] = useState("");
  const [department, setDepartment] = useState("");
  const [dob, setDob] = useState("");
  const [aadhar, setAadhar] = useState("");
  const [pan, setPan] = useState("");
  const [address, setAddress] = useState("");
  const [submittedAt, setSubmittedAt] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const fetchForm = async () => {
      try {
        const res = await fetch("http://localhost:8000/candidate-form", {
          headers: { "X-User-ID": String(currentUser.UserID) }
        });
        if (res.ok) {
          const data = await res.json();
          if (data) {
            setJoiningDate(data.JoiningDate?.substring(0, 10) || "");
            setPosition(data.Position || "");
            setDepartment(data.Department || "");
            setDob(data.DOB?.substring(0, 10) || "");
            setAadhar(data.Aadhar || "");
            setPan(data.PAN || "");
            setAddress(data.Address || "");
            setSubmittedAt(data.SubmittedAt?.substring(0, 10) || "");
          }
        }
      } catch (err) {
        console.error("Fetch failed", err);
      }
    };

    fetchForm();
  }, [currentUser]);

  const submit = async (e) => {
    e.preventDefault();
    setMessage("");

    const body = {
      JoiningDate: joiningDate || null,
      Position: position || null,
      Department: department || null,
      DOB: dob || null,
      Aadhar: aadhar || null,
      PAN: pan || null,
      Address: address || null,
      SubmittedAt: submittedAt || null
    };

    const res = await fetch("http://localhost:8000/candidate-form", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-ID": String(currentUser.UserID)
      },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      const err = await res.json();
      setMessage(err.detail || "Failed to save");
      return;
    }

    setMessage("Saved successfully");
  };

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Candidate Form</h2>

      <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={submit}>
        <label className="flex flex-col">
          <span>Joining Date (Tentative)</span>
          <input type="date" value={joiningDate}
                 onChange={(e) => setJoiningDate(e.target.value)}
                 className="border p-2 rounded" />
        </label>

        <label className="flex flex-col">
          <span>Position</span>
          <input value={position}
                 onChange={(e) => setPosition(e.target.value)}
                 className="border p-2 rounded" />
        </label>

        <label className="flex flex-col">
          <span>Department</span>
          <input value={department}
                 onChange={(e) => setDepartment(e.target.value)}
                 className="border p-2 rounded" />
        </label>

        <label className="flex flex-col">
          <span>Date of Birth</span>
          <input type="date" value={dob}
                 onChange={(e) => setDob(e.target.value)}
                 className="border p-2 rounded" />
        </label>

        <label className="flex flex-col">
          <span>Aadhar</span>
          <input value={aadhar}
                 onChange={(e) => setAadhar(e.target.value)}
                 className="border p-2 rounded"
                 maxLength={12} />
        </label>

        <label className="flex flex-col">
          <span>PAN</span>
          <input value={pan}
                 onChange={(e) => setPan(e.target.value)}
                 className="border p-2 rounded"
                 maxLength={10} />
        </label>

        <label className="flex flex-col md:col-span-2">
          <span>Address</span>
          <textarea value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    className="border p-2 rounded" />
        </label>

        <label className="flex flex-col md:col-span-2">
          <span>Submission Date</span>
          <input type="date" value={submittedAt}
                 onChange={(e) => setSubmittedAt(e.target.value)}
                 className="border p-2 rounded" />
        </label>

        {message && (
          <div className="md:col-span-2 text-green-600">{message}</div>
        )}

        <div className="md:col-span-2 flex justify-end">
          <button className="bg-blue-600 text-white px-4 py-2 rounded">Save</button>
        </div>
      </form>
    </div>
  );
}
