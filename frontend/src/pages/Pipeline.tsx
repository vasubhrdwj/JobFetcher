import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Badge } from "../components/ui";
import type { Application } from "../api/client";

const STATUS_ORDER: Application["status"][] = [
  "saved",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

const STATUS_COLORS: Record<Application["status"], "default" | "brand" | "green" | "yellow" | "red"> = {
  saved: "default",
  applied: "brand",
  interviewing: "yellow",
  offer: "green",
  rejected: "red",
  withdrawn: "default",
};

const STATUS_LABELS: Record<Application["status"], string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export default function Pipeline() {
  const queryClient = useQueryClient();
  const [filterStatus, setFilterStatus] = useState<string>("");

  const { data: applications = [], isLoading: appsLoading } = useQuery({
    queryKey: ["applications", filterStatus],
    queryFn: () =>
      api.applications.list(
        filterStatus ? { status: filterStatus } : undefined
      ),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: number;
      status: Application["status"];
    }) => api.applications.update(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["applications"] }),
  });

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Pipeline</h1>
        <p className="mt-1 text-sm text-gray-400">
          Track your job applications from saved to offer
        </p>
      </div>

      <div className="mb-6 flex gap-2 flex-wrap">
        <button
          onClick={() => setFilterStatus("")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
            !filterStatus
              ? "bg-brand-600/20 text-brand-300"
              : "bg-gray-800 text-gray-400 hover:text-gray-300"
          }`}
        >
          All
        </button>
        {STATUS_ORDER.map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
              filterStatus === s
                ? "bg-brand-600/20 text-brand-300"
                : "bg-gray-800 text-gray-400 hover:text-gray-300"
            }`}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}
      </div>

      {appsLoading ? (
        <div className="text-gray-500 text-center py-12">Loading...</div>
      ) : applications.length === 0 ? (
        <div className="text-gray-500 text-center py-12">
          No applications yet. Save a job to start tracking.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {applications.map((app) => (
            <div
              key={app.id}
              className="bg-gray-900 rounded-xl border border-gray-800 p-5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <Badge variant={STATUS_COLORS[app.status]}>
                    {STATUS_LABELS[app.status]}
                  </Badge>
                  {app.match_score !== null && (
                    <span className="ml-2 text-xs text-gray-500">
                      {Math.round(app.match_score * 100)}% match
                    </span>
                  )}
                </div>
                <select
                  value={app.status}
                  onChange={(e) =>
                    updateMutation.mutate({
                      id: app.id,
                      status: e.target.value as Application["status"],
                    })
                  }
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-400"
                >
                  {STATUS_ORDER.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>
              <p className="mt-3 text-sm text-gray-400">Job #{app.job_id}</p>
              {app.applied_at && (
                <p className="mt-1 text-xs text-gray-600">
                  Applied: {new Date(app.applied_at).toLocaleDateString()}
                </p>
              )}
              {app.next_follow_up_at && (
                <p className="mt-1 text-xs text-yellow-600">
                  Follow up by:{" "}
                  {new Date(app.next_follow_up_at).toLocaleDateString()}
                </p>
              )}
              {app.notes && (
                <p className="mt-2 text-xs text-gray-500 line-clamp-2">
                  {app.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}