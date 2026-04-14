

import { useEffect, useState } from "react";
import { getCandidateById } from "../../services/api/candidates";

export default function ProfileTab({ candidateId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!candidateId) return;

    let isMounted = true;

    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError("");

        const result = await getCandidateById(candidateId);

        if (isMounted) {
          setData(result || null);
        }
      } catch (err) {
        if (isMounted) {
          setError(err?.message || "Failed to load profile");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchProfile();

    return () => {
      isMounted = false;
    };
  }, [candidateId]);


  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        Loading candidate profile...
      </div>
    );
  }


  if (error) {
    return (
      <div className="p-6 text-center text-red-500">
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 text-center text-gray-400">
        No profile data available
      </div>
    );
  }

  return (
    <div className="grid gap-6">

      <section className="bg-white border rounded-2xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">
          Basic Information
        </h3>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <Info label="Name" value={data.candidate_name} />
          <Info label="Email" value={data.candidate_email} />
          <Info label="Phone" value={data.candidate_mobile} />
          <Info label="Role" value={data.candidate_role} />
          <Info label="Verified" value={data.candidate_is_verified ? "Yes" : "No"} />
        </div>
      </section>

     
      <section className="bg-white border rounded-2xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">
          Personal Information
        </h3>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <Info label="DOB" value={data.personal_info?.dob} />
          <Info label="Gender" value={data.personal_info?.gender} />
          <Info label="Department" value={data.personal_info?.department} />
          <Info label="Nationality" value={data.personal_info?.nationality} />
          <Info label="Current Address" value={data.personal_info?.current_address} />
          <Info label="Permanent Address" value={data.personal_info?.permanent_address} />
        </div>
      </section>

      
      <section className="bg-white border rounded-2xl p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-500 mb-3 uppercase tracking-wide">
          Documents
        </h3>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <Info label="Aadhar Number" value={data.aadhar?.aadhar} />
          <Info label="Aadhar Verified" value={data.aadhar?.is_verified ? "Yes" : "No"} />
          <Info label="PAN Number" value={data.pan?.pan} />
          <Info label="PAN Verified" value={data.pan?.is_verified ? "Yes" : "No"} />
        </div>
      </section>

    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="text-gray-400 text-xs">{label}</div>
      <div className="font-medium text-gray-900">
        {value || "-"}
      </div>
    </div>
  );
}