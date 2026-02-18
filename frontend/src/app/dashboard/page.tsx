"use client";

import { useEffect, useState } from "react";
import { dashboardService } from "@/services/dashboardService";
import { claimService } from "@/services/claimService";
import type { OverviewMetrics, Claim } from "@/types";
import { demoOverviewMetrics, demoClaims } from "@/lib/demoData";
import StatsCard from "@/components/dashboard/StatsCard";
import ChartCard from "@/components/dashboard/ChartCard";
import ClaimStatusBadge from "@/components/claims/ClaimStatusBadge";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
    FileText,
    AlertTriangle,
    DollarSign,
    Clock,
    Loader2,
} from "lucide-react";
import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
    Tooltip,
    Legend,
} from "recharts";

const STATUS_COLORS: Record<string, string> = {
    SUBMITTED: "#3b82f6",
    UNDER_REVIEW: "#f59e0b",
    APPROVED: "#10b981",
    REJECTED: "#ef4444",
    MANUAL_REVIEW_REQUIRED: "#8b5cf6",
    SETTLED: "#14b8a6",
};

export default function DashboardPage() {
    const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
    const [recentClaims, setRecentClaims] = useState<Claim[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [m, claimRes] = await Promise.all([
                    dashboardService.getOverview().catch(() => null),
                    claimService.list({ limit: 5 }).catch(() => null),
                ]);
                setMetrics(m ?? demoOverviewMetrics);
                setRecentClaims(claimRes?.claims ?? demoClaims.slice(0, 5));
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 size={32} className="animate-spin text-indigo-500" />
            </div>
        );
    }

    const pieData = metrics
        ? Object.entries(metrics.status_breakdown).map(([name, value]) => ({
            name: name.replace(/_/g, " "),
            value,
            fill: STATUS_COLORS[name] || "#6b7280",
        }))
        : [];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Dashboard</h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Overview of your insurance platform
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatsCard
                    title="Total Claims"
                    value={metrics?.total_claims ?? 0}
                    subtitle={`${metrics?.recent_claims_30d ?? 0} in last 30 days`}
                    icon={FileText}
                />
                <StatsCard
                    title="Pending Review"
                    value={metrics?.pending_manual_review ?? 0}
                    icon={Clock}
                    iconColor="text-amber-500"
                />
                <StatsCard
                    title="Total Settled"
                    value={formatCurrency(metrics?.total_settled_amount ?? 0)}
                    icon={DollarSign}
                    iconColor="text-emerald-500"
                />
                <StatsCard
                    title="Avg Fraud Score"
                    value={`${((metrics?.average_fraud_score ?? 0) * 100).toFixed(1)}%`}
                    icon={AlertTriangle}
                    iconColor="text-red-500"
                />
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
                {/* Status Breakdown */}
                <ChartCard title="Claim Status Breakdown" subtitle="Current distribution">
                    {pieData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={100}
                                    paddingAngle={4}
                                    dataKey="value"
                                >
                                    {pieData.map((entry, i) => (
                                        <Cell key={i} fill={entry.fill} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend
                                    verticalAlign="bottom"
                                    iconType="circle"
                                    formatter={(value) => (
                                        <span className="text-xs capitalize">{value}</span>
                                    )}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)] text-sm">
                            No data available
                        </div>
                    )}
                </ChartCard>

                {/* Recent Claims */}
                <ChartCard title="Recent Claims" subtitle="Latest submissions">
                    {recentClaims.length > 0 ? (
                        <div className="space-y-3">
                            {recentClaims.map((claim) => (
                                <div
                                    key={claim.id}
                                    className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-muted)] hover:bg-[var(--color-muted)]/80 transition-colors cursor-pointer"
                                >
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">
                                            {claim.policy_number}
                                        </p>
                                        <p className="text-xs text-[var(--color-muted-foreground)]">
                                            {claim.claim_type} · {formatDate(claim.created_at)}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm font-semibold">
                                            {formatCurrency(claim.claim_amount)}
                                        </span>
                                        <ClaimStatusBadge status={claim.status} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)] text-sm">
                            No recent claims
                        </div>
                    )}
                </ChartCard>
            </div>
        </div>
    );
}
