"use client";

import { useEffect, useState } from "react";
import { dashboardService } from "@/services/dashboardService";
import type { FraudDistribution, ComplianceSummary } from "@/types";
import { demoFraudDistribution, demoComplianceSummary } from "@/lib/demoData";
import ChartCard from "@/components/dashboard/ChartCard";
import StatsCard from "@/components/dashboard/StatsCard";
import { Loader2, ShieldCheck, AlertTriangle, UserCheck, BarChart3 } from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";

export default function FraudOverviewPage() {
    const [fraud, setFraud] = useState<FraudDistribution | null>(null);
    const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [f, c] = await Promise.all([
                    dashboardService.getFraudDistribution().catch(() => null),
                    dashboardService.getComplianceSummary().catch(() => null),
                ]);
                setFraud(f ?? demoFraudDistribution);
                setCompliance(c ?? demoComplianceSummary);
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

    const barData = fraud
        ? Object.entries(fraud.buckets).map(([bucket, count]) => ({
            range: bucket,
            count,
        }))
        : [];

    const getBarColor = (range: string) => {
        if (range.startsWith("0")) return "#10b981";
        if (range.startsWith("0.2") || range.startsWith("0.3")) return "#f59e0b";
        if (range.startsWith("0.4") || range.startsWith("0.5")) return "#f97316";
        return "#ef4444";
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Fraud & Compliance</h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Fraud risk overview and compliance health
                </p>
            </div>

            {/* Compliance Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatsCard
                    title="Fraud Analyzed"
                    value={compliance?.claims_with_fraud_analysis ?? 0}
                    icon={BarChart3}
                />
                <StatsCard
                    title="High Risk"
                    value={compliance?.high_risk_claims ?? 0}
                    icon={AlertTriangle}
                    iconColor="text-red-500"
                />
                <StatsCard
                    title="Human Review"
                    value={compliance?.human_review_required_count ?? 0}
                    icon={UserCheck}
                    iconColor="text-amber-500"
                />
                <StatsCard
                    title="Compliance Rate"
                    value={`${((compliance?.compliance_rate ?? 0) * 100).toFixed(1)}%`}
                    icon={ShieldCheck}
                    iconColor="text-emerald-500"
                />
            </div>

            {/* Fraud Heatmap Style Bar Chart */}
            <ChartCard
                title="Fraud Score Distribution"
                subtitle="Claims by fraud risk bucket — color-coded by severity"
            >
                {barData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={320}>
                        <BarChart data={barData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                            <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 12 }} />
                            <Tooltip />
                            <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
                                {barData.map((entry, i) => (
                                    <Cell key={i} fill={getBarColor(entry.range)} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex items-center justify-center h-64 text-sm text-[var(--color-muted-foreground)]">
                        No fraud distribution data available
                    </div>
                )}
            </ChartCard>

            {/* Overrides info */}
            {compliance && (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5">
                    <h3 className="font-semibold mb-3">Override Summary</h3>
                    <div className="grid sm:grid-cols-2 gap-4 text-sm">
                        <div className="flex justify-between p-3 rounded-lg bg-[var(--color-muted)]">
                            <span className="text-[var(--color-muted-foreground)]">
                                Fraud Score Overrides
                            </span>
                            <span className="font-semibold">
                                {compliance.fraud_score_overrides}
                            </span>
                        </div>
                        <div className="flex justify-between p-3 rounded-lg bg-[var(--color-muted)]">
                            <span className="text-[var(--color-muted-foreground)]">
                                Human Review Required
                            </span>
                            <span className="font-semibold">
                                {compliance.human_review_required_count}
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
