import { useEffect, useMemo, useState } from "react";
import { getCandidateById } from "../../services/api/candidates";

export default function ProfileTab({ candidateId, candidate }) {
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

  const profile = useMemo(() => {
    return {
      ...(candidate || {}),
      ...(data || {}),
    };
  }, [candidate, data]);

  const skills = useMemo(() => {
    const rawSkills =
      profile?.candidate_skills || profile?.skills || profile?.skill_set || "";

    if (Array.isArray(rawSkills)) {
      return rawSkills.filter(Boolean);
    }

    if (typeof rawSkills === "string") {
      return rawSkills
        .split(",")
        .map((skill) => skill.trim())
        .filter(Boolean);
    }

    return [];
  }, [profile]);

  const educationRecords = Array.isArray(profile?.education_records)
    ? profile.education_records
    : [];

  const experienceRecords = Array.isArray(profile?.experience_records)
    ? profile.experience_records
    : [];

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        Loading candidate profile...
      </div>
    );
  }

  if (error) {
    return <div className="p-6 text-center text-red-500">{error}</div>;
  }

  if (!profile || (!data && !candidate)) {
    return (
      <div className="p-6 text-center text-gray-400">
        No profile data available
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Candidate Overview" />

        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-4">
          <Info
            label="Available To Join"
            value={
              profile?.candidate_joining_date ||
              profile?.joining_date ||
              profile?.available_to_join
            }
          />
          <Info
            label="Experience"
            value={
              profile?.candidate_experience ||
              profile?.experience ||
              profile?.total_experience
            }
          />
          <Info
            label="Location"
            value={
              profile?.candidate_current_location ||
              profile?.current_location ||
              profile?.location
            }
          />
          <Info
            label="Current Salary"
            value={
              profile?.candidate_current_salary ||
              profile?.current_salary ||
              profile?.current_ctc
            }
          />
          <Info
            label="Expected Salary"
            value={
              profile?.candidate_expected_salary ||
              profile?.expected_salary ||
              profile?.expected_ctc
            }
          />
        </div>

        <div className="mt-5">
          <Info
            label="Source"
            value={profile?.candidate_source || profile?.source}
          />
        </div>

        <div className="mt-5">
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-600 mb-1.5">
              Skills
            </div>

            {skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded-full bg-white border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <div className="text-sm font-semibold text-gray-900 break-words leading-relaxed">
                -
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Basic Information" />

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <Info
            label="Name"
            value={
              profile?.candidate_name ||
              profile?.name ||
              `${profile?.first_name || ""} ${profile?.last_name || ""}`.trim()
            }
          />
          <Info
            label="Email"
            value={profile?.candidate_email || profile?.email}
          />
          <Info
            label="Phone"
            value={profile?.candidate_mobile || profile?.phone}
          />
          <Info
            label="Role"
            value={profile?.candidate_role || profile?.jobTitle}
          />
          <Info
            label="Verified"
            value={profile?.candidate_is_verified ? "Yes" : "No"}
          />
        </div>
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Personal Information" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Info label="DOB" value={profile?.personal_info?.dob} />
          <Info label="Gender" value={profile?.personal_info?.gender} />
          <Info label="Department" value={profile?.personal_info?.department} />
          <Info
            label="Nationality"
            value={profile?.personal_info?.nationality}
          />
          <Info
            label="Current Address"
            value={profile?.personal_info?.current_address}
          />
          <Info
            label="Permanent Address"
            value={profile?.personal_info?.permanent_address}
          />
        </div>
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Education Details" />

        {educationRecords.length > 0 ? (
          <div className="grid gap-4">
            {educationRecords.map((item, index) => (
              <div
                key={item?.id || index}
                className="rounded-xl border border-gray-100 bg-gray-50 p-4"
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Info label="Qualification" value={item?.qualification} />
                  <Info label="Institute" value={item?.institute_name} />
                  <Info label="Year" value={item?.year_of_passing} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyText />
        )}
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Experience Details" />

        {experienceRecords.length > 0 ? (
          <div className="grid gap-4">
            {experienceRecords.map((item, index) => (
              <div
                key={item?.id || index}
                className="rounded-xl border border-gray-100 bg-gray-50 p-4"
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Info label="Company" value={item?.company_name} />
                  <Info label="Designation" value={item?.designation} />
                  <Info label="Duration" value={item?.duration} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyText />
        )}
      </section>

      <section className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
        <SectionTitle title="Documents" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Info label="Aadhar Number" value={profile?.aadhar?.aadhar} />
          <Info
            label="Aadhar Verified"
            value={profile?.aadhar?.is_verified ? "Yes" : "No"}
          />
          <Info label="PAN Number" value={profile?.pan?.pan} />
          <Info
            label="PAN Verified"
            value={profile?.pan?.is_verified ? "Yes" : "No"}
          />
        </div>
      </section>
    </div>
  );
}

function SectionTitle({ title }) {
  return (
    <h3 className="text-sm font-semibold text-gray-500 mb-4 uppercase tracking-wide">
      {title}
    </h3>
  );
}

function Info({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-600 mb-1.5">
        {label}
      </div>

      <div className="text-sm font-semibold text-gray-900 break-words leading-relaxed">
        {value || "-"}
      </div>
    </div>
  );
}

function EmptyText() {
  return <div className="text-sm text-gray-400">No data available</div>;
}
