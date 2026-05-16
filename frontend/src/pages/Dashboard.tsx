import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatCard } from "../components/ui";

export default function Dashboard() {
  const { data: companiesData, isLoading: companiesLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: () => api.companies.list(),
  });

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.jobs.list({ limit: "1" }),
  });

  const { data: applicationsData, isLoading: applicationsLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => api.applications.list(),
  });

  const companyCount = companiesData?.total ?? 0;
  const jobCount = jobsData?.total ?? 0;
  const applicationCount = applicationsData?.length ?? 0;

  const atsBreakdown = companiesData?.companies.reduce(
    (acc, c) => {
      acc[c.ats_platform] = (acc[c.ats_platform] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-400">
          AI-powered job intelligence for software engineers
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Companies Tracked"
          value={companiesLoading ? "..." : companyCount}
          sub="Top SE employers"
        />
        <StatCard
          label="Active Jobs"
          value={jobsLoading ? "..." : jobCount}
          sub="Across all sources"
        />
        <StatCard
          label="Applications"
          value={applicationsLoading ? "..." : applicationCount}
          sub="In pipeline"
        />
        <StatCard
          label="ATS Coverage"
          value={
            atsBreakdown
              ? Object.keys(atsBreakdown).length
              : "..."
          }
          sub="Parser platforms"
        />
      </div>

      {atsBreakdown && (
        <div className="mt-8 bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">
            ATS Platform Distribution
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(atsBreakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([platform, count]) => (
                <div
                  key={platform}
                  className="bg-gray-800 rounded-lg p-3 text-center"
                >
                  <p className="text-2xl font-bold text-brand-400">{count}</p>
                  <p className="text-xs text-gray-400 mt-1 capitalize">
                    {platform}
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="mt-8 bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">
          Build Phases
        </h2>
        <div className="space-y-3">
          {[
            {
              phase: "Phase 1",
              name: "Project Scaffold & Data Foundation",
              status: "done",
            },
            {
              phase: "Phase 2",
              name: "Scraping Engine",
              status: "next",
            },
            { phase: "Phase 3", name: "Profile & Scoring", status: "pending" },
            {
              phase: "Phase 4",
              name: "Application Optimization",
              status: "pending",
            },
            {
              phase: "Phase 5",
              name: "Pipeline & Tracking",
              status: "pending",
            },
            {
              phase: "Phase 6",
              name: "Continuous Intelligence",
              status: "pending",
            },
          ].map((p) => (
            <div
              key={p.phase}
              className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-800/50"
            >
              <div>
                <span className="text-sm font-medium text-gray-300">
                  {p.phase}:
                </span>
                <span className="ml-2 text-sm text-gray-400">{p.name}</span>
              </div>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  p.status === "done"
                    ? "bg-green-900/40 text-green-400"
                    : p.status === "next"
                      ? "bg-brand-600/20 text-brand-300"
                      : "bg-gray-800 text-gray-500"
                }`}
              >
                {p.status === "done"
                  ? "Complete"
                  : p.status === "next"
                    ? "Up Next"
                    : "Planned"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}