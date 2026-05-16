import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Badge } from "../components/ui";

export default function Companies() {
  const [page, setPage] = useState(0);
  const [atsFilter, setAtsFilter] = useState<string>("");
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["companies", page, atsFilter],
    queryFn: () =>
      api.companies.list({
        skip: String(page * limit),
        limit: String(limit),
        ...(atsFilter ? { ats_platform: atsFilter } : {}),
      }),
  });

  const atsOptions = [
    { value: "", label: "All Platforms" },
    { value: "greenhouse", label: "Greenhouse" },
    { value: "lever", label: "Lever" },
    { value: "workday", label: "Workday" },
    { value: "icims", label: "iCIMS" },
    { value: "ashby", label: "Ashby" },
    { value: "custom", label: "Custom" },
  ];

  return (
    <div>
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            Companies ({data?.total ?? "..."})
          </h1>
          <p className="mt-1 text-sm text-gray-400">
            Top 100 SE companies tracked in real-time
          </p>
        </div>
        <select
          value={atsFilter}
          onChange={(e) => {
            setAtsFilter(e.target.value);
            setPage(0);
          }}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        >
          {atsOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading...</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data?.companies.map((company) => (
              <div
                key={company.id}
                className="bg-gray-900 rounded-xl border border-gray-800 p-5 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-100">
                      {company.name}
                    </h3>
                    {company.industry && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {company.industry}
                      </p>
                    )}
                  </div>
                  <Badge variant={company.is_active ? "green" : "default"}>
                    {company.ats_platform}
                  </Badge>
                </div>
                <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                  {company.headquarters && <span>{company.headquarters}</span>}
                  {company.size && <span>{company.size} employees</span>}
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    {company.job_count}{" "}
                    {company.job_count === 1 ? "job" : "jobs"}
                  </span>
                  <a
                    href={company.career_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brand-400 hover:text-brand-300"
                  >
                    Career Page &rarr;
                  </a>
                </div>
                {company.last_scraped_at && (
                  <p className="mt-2 text-xs text-gray-600">
                    Last scraped:{" "}
                    {new Date(company.last_scraped_at).toLocaleDateString()}
                  </p>
                )}
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