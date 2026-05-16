import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Badge } from "../components/ui";

export default function Jobs() {
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [remoteFilter, setRemoteFilter] = useState<string>("");
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", page, search, remoteFilter],
    queryFn: () =>
      api.jobs.list({
        skip: String(page * limit),
        limit: String(limit),
        ...(search ? { search } : {}),
        ...(remoteFilter ? { is_remote: remoteFilter } : {}),
      }),
  });

  return (
    <div>
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Jobs ({data?.total ?? "..."})
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            SE roles from top companies, updated every 2-4 hours
          </p>
        </div>
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search job titles..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 placeholder-gray-600 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
          <select
            value={remoteFilter}
            onChange={(e) => {
              setRemoteFilter(e.target.value);
              setPage(0);
            }}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300"
          >
            <option value="">All types</option>
            <option value="true">Remote only</option>
            <option value="false">Onsite only</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading...</div>
      ) : !data?.jobs.length ? (
        <div className="text-gray-500 text-center py-12">
          No jobs found. Run the scraper to populate jobs.
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {data?.jobs.map((job) => (
              <div
                key={job.id}
                className="bg-gray-900 rounded-xl border border-gray-800 p-5 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-100">
                      {job.title}
                    </h3>
                    <p className="text-sm text-gray-400 mt-0.5">
                      {job.company_name}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {job.is_remote && (
                      <Badge variant="green">Remote</Badge>
                    )}
                    {job.seniority && <Badge>{job.seniority}</Badge>}
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                  {job.location && <span>{job.location}</span>}
                  {job.salary_min && job.salary_max && (
                    <span>
                      ${job.salary_min / 1000}k - ${job.salary_max / 1000}k
                    </span>
                  )}
                  <span>
                    Discovered{" "}
                    {new Date(job.discovered_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="mt-3 flex justify-end">
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brand-400 hover:text-brand-300"
                  >
                    View Posting &rarr;
                  </a>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-4 py-2 bg-gray-800 rounded-lg text-sm text-gray-300 disabled:opacity-50 hover:bg-gray-700"
            >
              Previous
            </button>
            <span className="text-sm text-gray-500">
              Page {page + 1} of {Math.ceil((data?.total ?? 0) / limit)}
            </span>
            <button
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * limit >= (data?.total ?? 0)}
              className="px-4 py-2 bg-gray-800 rounded-lg text-sm text-gray-300 disabled:opacity-50 hover:bg-gray-700"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}