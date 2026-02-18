import api from "./api";
import type { OverviewMetrics, FraudDistribution, SLAMetrics, ComplianceSummary } from "@/types";

export const dashboardService = {
    async getOverview(): Promise<OverviewMetrics> {
        const res = await api.get<OverviewMetrics>("/dashboard/overview");
        return res.data;
    },

    async getFraudDistribution(): Promise<FraudDistribution> {
        const res = await api.get<FraudDistribution>("/dashboard/fraud-distribution");
        return res.data;
    },

    async getSLAMetrics(): Promise<SLAMetrics> {
        const res = await api.get<SLAMetrics>("/dashboard/sla");
        return res.data;
    },

    async getComplianceSummary(): Promise<ComplianceSummary> {
        const res = await api.get<ComplianceSummary>("/dashboard/compliance");
        return res.data;
    },
};
