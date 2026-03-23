// Main dashboard cards and quick actions.
import {
  BadgeDollarSign,
  Briefcase,
  Calendar,
  LayoutDashboard,
  Plus,
  Search,
  Users
} from "lucide-react";
import { Button, Card, StatusBadge } from "../components/ui";

function StatCard({ title, value, icon, onClick }) {
  return (
    <button
      onClick={onClick}
      className="rounded-2xl border bg-white p-5 text-left shadow-sm transition hover:shadow"
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-gray-600">{title}</div>
        <div className="text-gray-700">{icon}</div>
      </div>
      <div className="mt-2 text-3xl font-extrabold tracking-tight">{value}</div>
    </button>
  );
}

export default function Dashboard({ candidates, jobs, interviews, offers = [], onGo }) {
  const openJobs = jobs.filter((j) => j.status === "Open" || j.status === "Public").length;
  const inPipeline = candidates.filter((c) => c.status !== "Rejected").length;
  const scheduled = interviews.filter((i) => i.status === "Scheduled").length;
  const pendingOffers = offers.filter((o) => o.offer_status === "Pending").length;
  const latestOffer = offers.length ? offers[offers.length - 1] : null;

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Open Jobs"
          value={String(openJobs)}
          icon={<Briefcase className="h-4 w-4" />}
          onClick={() => onGo("jobs")}
        />
        <StatCard
          title="Candidates in Pipeline"
          value={String(inPipeline)}
          icon={<Users className="h-4 w-4" />}
          onClick={() => onGo("candidateSearch")}
        />
        <StatCard
          title="Interviews Scheduled"
          value={String(scheduled)}
          icon={<Calendar className="h-4 w-4" />}
          onClick={() => onGo("interviewStatus")}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Quick actions" icon={<LayoutDashboard className="h-4 w-4" />}>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => onGo("candidateCreate")}>
              <Plus className="h-4 w-4" /> Add New Candidate
            </Button>
            <Button variant="secondary" onClick={() => onGo("candidateSearch")}>
              <Search className="h-4 w-4" /> Search Candidate
            </Button>
            <Button variant="secondary" onClick={() => onGo("jobs")}>
              <Plus className="h-4 w-4" /> Create Job
            </Button>
          </div>
        </Card>

        <Card title="Offer snapshot" icon={<BadgeDollarSign className="h-4 w-4" />}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-gray-900">
                {pendingOffers ? `${pendingOffers} pending` : "No offers"}
              </div>
              {latestOffer ? (
                <>
                  <div className="mt-1 text-xs text-gray-600">
                    Latest: <span className="font-semibold">{latestOffer.position}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-600">
                    Salary:{" "}
                    <span className="font-semibold">
                      ${String(latestOffer.salary || 0)}
                    </span>
                  </div>
                </>
              ) : null}
            </div>
            {latestOffer ? (
              <StatusBadge status={latestOffer.offer_status} />
            ) : null}
          </div>
          <Button
            variant="secondary"
            className="mt-3 w-full"
            onClick={() => onGo("offer")}
          >
            Manage Offers
          </Button>
        </Card>
      </div>
    </div>
  );
}
