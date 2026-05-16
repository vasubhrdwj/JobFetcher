import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { UserProfile } from "../api/client";

export default function Profile() {
  const queryClient = useQueryClient();
  const { data: profiles = [] } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => api.profiles.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<UserProfile>) => api.profiles.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profiles"] }),
  });

  const [form, setForm] = useState({
    name: "",
    email: "",
    target_role: "",
    experience_years: "",
    skills: "",
    target_companies: "",
    target_locations: "",
    min_salary: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      name: form.name || null,
      email: form.email,
      target_role: form.target_role || null,
      experience_years: form.experience_years ? parseInt(form.experience_years) : null,
      skills: form.skills ? form.skills.split(",").map((s) => s.trim()) : null,
      target_companies: form.target_companies
        ? form.target_companies.split(",").map((s) => s.trim())
        : null,
      target_locations: form.target_locations
        ? form.target_locations.split(",").map((s) => s.trim())
        : null,
      min_salary: form.min_salary ? parseInt(form.min_salary) : null,
    });
  };

  const activeProfile = profiles[0];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Profile</h1>
        <p className="mt-1 text-sm text-gray-400">
          Your career profile — powers job matching, scoring, and resume tailoring
        </p>
      </div>

      {activeProfile && (
        <div className="mb-8 bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">
            Active Profile
          </h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <dt className="text-xs text-gray-500">Name</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.name || "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Email</dt>
              <dd className="text-sm text-gray-200">{activeProfile.email}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Target Role</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.target_role || "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Experience</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.experience_years
                  ? `${activeProfile.experience_years} years`
                  : "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Skills</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.skills?.join(", ") || "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Target Companies</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.target_companies?.join(", ") || "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Target Locations</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.target_locations?.join(", ") || "Not set"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Min Salary</dt>
              <dd className="text-sm text-gray-200">
                {activeProfile.min_salary
                  ? `$${(activeProfile.min_salary / 1000).toFixed(0)}k`
                  : "Not set"}
              </dd>
            </div>
          </dl>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4"
      >
        <h2 className="text-lg font-semibold text-gray-100">
          {activeProfile ? "Update Profile" : "Create Profile"}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Jane Smith"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Email *
            </label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="jane@example.com"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Target Role
            </label>
            <input
              type="text"
              value={form.target_role}
              onChange={(e) =>
                setForm({ ...form, target_role: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Senior Backend Engineer"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Years of Experience
            </label>
            <input
              type="number"
              value={form.experience_years}
              onChange={(e) =>
                setForm({ ...form, experience_years: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="5"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs text-gray-500 mb-1">
              Skills (comma-separated)
            </label>
            <input
              type="text"
              value={form.skills}
              onChange={(e) => setForm({ ...form, skills: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Python, React, PostgreSQL, AWS, Kubernetes"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs text-gray-500 mb-1">
              Target Companies (comma-separated)
            </label>
            <input
              type="text"
              value={form.target_companies}
              onChange={(e) =>
                setForm({ ...form, target_companies: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Stripe, Figma, Databricks"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs text-gray-500 mb-1">
              Target Locations (comma-separated)
            </label>
            <input
              type="text"
              value={form.target_locations}
              onChange={(e) =>
                setForm({ ...form, target_locations: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="San Francisco, Remote, New York"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Min Salary ($)
            </label>
            <input
              type="number"
              value={form.min_salary}
              onChange={(e) =>
                setForm({ ...form, min_salary: e.target.value })
              }
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="150000"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={createMutation.isPending}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {createMutation.isPending ? "Saving..." : "Save Profile"}
        </button>
      </form>
    </div>
  );
}