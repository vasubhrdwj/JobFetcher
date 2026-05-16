const API_BASE = "/api/v1";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API error");
  }
  return res.json();
}

export interface Company {
  id: number;
  name: string;
  career_url: string;
  ats_platform: string;
  industry: string | null;
  logo_url: string | null;
  headquarters: string | null;
  size: string | null;
  is_active: boolean;
  job_count: number;
  last_scraped_at: string | null;
  scrape_status: string | null;
}

export interface CompanyList {
  companies: Company[];
  total: number;
}

export interface Job {
  id: number;
  company_id: number;
  title: string;
  description: string | null;
  location: string | null;
  job_type: string | null;
  seniority: string | null;
  salary_min: number | null;
  salary_max: number | null;
  requirements: Record<string, unknown> | null;
  responsibilities: Record<string, unknown> | null;
  url: string;
  source: string;
  is_remote: boolean | null;
  posted_at: string | null;
  discovered_at: string;
  is_active: boolean;
  company_name: string | null;
}

export interface JobList {
  jobs: Job[];
  total: number;
}

export interface Application {
  id: number;
  user_id: number;
  job_id: number;
  status: "saved" | "applied" | "interviewing" | "offer" | "rejected" | "withdrawn";
  applied_at: string | null;
  notes: string | null;
  next_follow_up_at: string | null;
  match_score: number | null;
}

export interface UserProfile {
  id: number;
  name: string | null;
  email: string;
  target_role: string | null;
  target_companies: string[] | null;
  target_locations: string[] | null;
  min_salary: number | null;
  skills: string[] | null;
  experience_years: number | null;
  education: Record<string, unknown> | null;
  resume_text: string | null;
  preferences: Record<string, unknown> | null;
}

export const api = {
  companies: {
    list: (params?: Record<string, string>) => {
      const qs = params ? "?" + new URLSearchParams(params).toString() : "";
      return fetchAPI<CompanyList>(`/companies/${qs}`);
    },
    get: (id: number) => fetchAPI<Company>(`/companies/${id}`),
  },
  jobs: {
    list: (params?: Record<string, string>) => {
      const qs = params ? "?" + new URLSearchParams(params).toString() : "";
      return fetchAPI<JobList>(`/jobs/${qs}`);
    },
    get: (id: number) => fetchAPI<Job>(`/jobs/${id}`),
  },
  applications: {
    list: (params?: Record<string, string>) => {
      const qs = params ? "?" + new URLSearchParams(params).toString() : "";
      return fetchAPI<Application[]>(`/applications/${qs}`);
    },
    create: (data: Partial<Application>) =>
      fetchAPI<Application>("/applications/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: Partial<Application>) =>
      fetchAPI<Application>(`/applications/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
  profiles: {
    list: () => fetchAPI<UserProfile[]>("/profiles/"),
    get: (id: number) => fetchAPI<UserProfile>(`/profiles/${id}`),
    create: (data: Partial<UserProfile>) =>
      fetchAPI<UserProfile>("/profiles/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  health: () => fetchAPI<{ status: string; version: string }>("/health"),
};