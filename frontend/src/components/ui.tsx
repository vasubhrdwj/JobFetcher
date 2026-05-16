export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
}

export function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <p className="text-sm font-medium text-gray-400">{label}</p>
      <p className="mt-2 text-3xl font-bold text-gray-100">{value}</p>
      {sub && <p className="mt-1 text-sm text-gray-500">{sub}</p>}
    </div>
  );
}

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "brand" | "green" | "yellow" | "red";
}

export function Badge({ children, variant = "default" }: BadgeProps) {
  const colors = {
    default: "bg-gray-800 text-gray-300",
    brand: "bg-brand-600/20 text-brand-300",
    green: "bg-green-900/40 text-green-400",
    yellow: "bg-yellow-900/40 text-yellow-400",
    red: "bg-red-900/40 text-red-400",
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[variant]}`}
    >
      {children}
    </span>
  );
}