import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Badge } from "../components/ui";

type ScrapeResult = {
  company?: string;
  status?: string;
  message?: string;
  total_jobs?: number;
  new_jobs?: number;
};

export default function Scraper() {
  const queryClient = useQueryClient();
  const [runResult, setRunResult] = useState<ScrapeResult | null>(null);
  const [companyScrapeResult, setCompanyScrapeResult] = useState<ScrapeResult | null>(null);

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["scraper-status"],
    queryFn: () => api.scraper.status(),
    refetchInterval: 10000,
  });

  const scrapeAllMutation = useMutation({
    mutationFn: () => api.scraper.run(),
    onSuccess: (data) => {
      setRunResult(data);
      queryClient.invalidateQueries({ queryKey: ["scraper-status"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const { data: companiesData } = useQuery({
    queryKey: ["companies"],
    queryFn: () => api.companies.list({ limit: "200" }),
  });

  const scrapeCompanyMutation = useMutation({
    mutationFn: (id: number) => api.scraper.runCompany(id),
    onSuccess: (data) => {
      setCompanyScrapeResult(data);
      queryClient.invalidateQueries({ queryKey: ["scraper-status"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Scraper</h1>
        <p className="mt-1 text-sm text-gray-400">
          Fetch jobs from career pages — powered by ATS parsers + LLM extraction
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">
              Scrape All
            </h2>
            <button
              onClick={() => scrapeAllMutation.mutate()}
              disabled={scrapeAllMutation.isPending}
              className="w-full px-4 py-3 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {scrapeAllMutation.isPending
                ? "Scraping... (this takes a few minutes)"
                : "Run Full Scrape"}
            </button>
            {scrapeAllMutation.isError && (
              <div className="mt-3 p-3 bg-red-900/40 border border-red-800 rounded-lg">
                <p className="text-xs text-red-400">
                  Error: {(scrapeAllMutation.error as Error)?.message || "Unknown error"}
                </p>
              </div>
            )}
            {runResult && (
              <div className="mt-3 p-3 bg-green-900/40 border border-green-800 rounded-lg">
                <p className="text-xs text-green-400">{runResult.message}</p>
                <p className="text-xs text-gray-400 mt-1">
                  Status will update below as each company is scraped.
                </p>
              </div>
            )}

            <div className="mt-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Total companies</span>
                <span className="text-gray-200">
                  {status?.total_companies ?? "..."}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Scraped at least once</span>
                <span className="text-gray-200">
                  {status?.scraped_at_least_once ?? "..."}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">
              Scrape Single
            </h2>
            <select
              value={selectedCompanyId}
              onChange={(e) => setSelectedCompanyId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 mb-3"
            >
              <option value="">Select a company...</option>
              {companiesData?.companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.ats_platform})
                </option>
              ))}
            </select>
            <button
              onClick={() =>
                selectedCompanyId &&
                scrapeCompanyMutation.mutate(Number(selectedCompanyId))
              }
              disabled={!selectedCompanyId || scrapeCompanyMutation.isPending}
              className="w-full px-4 py-3 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {scrapeCompanyMutation.isPending
                ? "Scraping..."
                : "Scrape Selected Company"}
            </button>
            {companyScrapeResult && (
              <div className="mt-3 p-3 bg-gray-800 rounded-lg">
                <p className="text-sm font-medium text-gray-200">
                  {companyScrapeResult.company}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {companyScrapeResult.total_jobs} total,{" "}
                  {companyScrapeResult.new_jobs} new
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">
              Recent Scrapes
            </h2>
            {statusLoading ? (
              <div className="text-gray-500 text-center py-8">Loading...</div>
            ) : !status?.recent_scrapes?.length ? (
              <div className="text-gray-500 text-center py-8">
                No scrapes yet. Run a scrape to see results.
              </div>
            ) : (
              <div className="space-y-2">
                {status.recent_scrapes.map((s, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-800/50"
                  >
                    <span className="text-sm text-gray-200">{s.name}</span>
                    <div className="flex items-center gap-3">
                      {s.status?.startsWith("success") ? (
                        <Badge variant="green">OK</Badge>
                      ) : s.status ? (
                        <Badge variant="red">Error</Badge>
                      ) : (
                        <Badge>—</Badge>
                      )}
                      {s.last_scraped_at && (
                        <span className="text-xs text-gray-500">
                          {new Date(s.last_scraped_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="text-lg font-semibold text-gray-100 mb-3">
              ATS Parser Coverage
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              Each parser uses the platform's API (Greenhouse, Lever) or
              extracts job links from career pages (Workday, iCIMS, Custom). LLM
              extraction fills in details for parsers that only get titles/links.
            </p>
            {companiesData?.companies ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(
                  companiesData.companies.reduce(
                    (acc, c) => {
                      acc[c.ats_platform] =
                        (acc[c.ats_platform] || 0) + 1;
                      return acc;
                    },
                    {} as Record<string, number>
                  )
                )
                  .sort(([, a], [, b]) => b - a)
                  .map(([platform, count]) => (
                    <div
                      key={platform}
                      className="bg-gray-800 rounded-lg p-3 text-center"
                    >
                      <p className="text-xl font-bold text-brand-400">
                        {count}
                      </p>
                      <p className="text-xs text-gray-400 mt-1 capitalize">
                        {platform}
                      </p>
                    </div>
                  ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}