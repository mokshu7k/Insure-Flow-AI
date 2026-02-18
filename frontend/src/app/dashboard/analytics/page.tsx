"use client";

import { useEffect, useState } from "react";
import { dashboardService } from "@/services/dashboardService";
import type { SLAMetrics, FraudDistribution } from "@/types";
import { demoSLAMetrics, demoFraudDistribution } from "@/lib/demoData";
import ChartCard from "@/components/dashboard/ChartCard";
import { Loader2 } from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    AreaChart,
    Area,
} from "recharts";

export default function AnalyticsPage() {
    const [sla, setSla] = useState<SLAMetrics | null>(null);
    const [fraud, setFraud] = useState<FraudDistribution | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [s, f] = await Promise.all([
                    dashboardService.getSLAMetrics().catch(() => null),
                    dashboardService.getFraudDistribution().catch(() => null),
                ]);
                setSla(s ?? demoSLAMetrics);
                setFraud(f ?? demoFraudDistribution);
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

    const slaData = sla
        ? Object.entries(sla.by_type).map(([type, days]) => ({
            type: type.replace(/_/g, " "),
            days: Number(days.toFixed(1)),
        }))
        : [];

    const fraudData = fraud
        ? Object.entries(fraud.buckets).map(([bucket, count]) => ({
            range: bucket,
            count,
        }))
        : [];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Analytics</h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    SLA performance and fraud distribution
                </p>
            </div>

            {/* Summary cards */}
            <div className="grid sm:grid-cols-3 gap-4">
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                    <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                        Avg Days to Decision
                    </p>
                    <p className="text-2xl font-bold mt-1">
                        {sla?.average_days_to_decision?.toFixed(1) ?? "—"}
                    </p>
                </div>
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                    <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                        Total Assessed
                    </p>
                    <p className="text-2xl font-bold mt-1">
                        {fraud?.total_assessed ?? 0}
                    </p>
                </div>
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                    <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                        High Risk Claims
                    </p>
                    <p className="text-2xl font-bold text-red-500 mt-1">
                        {fraud?.high_risk_count ?? 0}
                    </p>
                </div>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
                {/* SLA by Type */}
                <ChartCard
                    title="SLA by Claim Type"
                    subtitle="Average days from submission to decision"
                >
                    {slaData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <BarChart data={slaData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                <XAxis dataKey="type" tick={{ fontSize: 12 }} />
                                <YAxis tick={{ fontSize: 12 }} />
                                <Tooltip />
                                <Bar
                                    dataKey="days"
                                    fill="#4f46e5"
                                    radius={[6, 6, 0, 0]}
                                    maxBarSize={48}
                                />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-64 text-sm text-[var(--color-muted-foreground)]">
                            No SLA data available
                        </div>
                    )}
                </ChartCard>

                {/* Fraud Distribution */}
                <ChartCard
                    title="Fraud Score Distribution"
                    subtitle={`Mean score: ${((fraud?.mean_score ?? 0) * 100).toFixed(1)}%`}
                >
                    {fraudData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={280}>
                            <AreaChart data={fraudData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                                <YAxis tick={{ fontSize: 12 }} />
                                <Tooltip />
                                <defs>
                                    <linearGradient id="fraudGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <Area
                                    type="monotone"
                                    dataKey="count"
                                    stroke="#ef4444"
                                    fill="url(#fraudGrad)"
                                    strokeWidth={2}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="flex items-center justify-center h-64 text-sm text-[var(--color-muted-foreground)]">
                            No fraud data available
                        </div>
                    )}
                </ChartCard>
            </div>
        </div>
    );
}
