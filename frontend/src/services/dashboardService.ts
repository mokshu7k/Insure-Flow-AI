import api from "./api";
import type { OverviewMetrics, FraudDistribution, SLAMetrics, ComplianceSummary, CustomerMetrics } from "@/types";

export const dashboardService = {
    overview: () => api.get<OverviewMetrics>("/dashboard/overview").then((r) => r.data),
    fraudDistribution: () => api.get<FraudDistribution>("/dashboard/fraud-distribution").then((r) => r.data),
    sla: () => api.get<SLAMetrics>("/dashboard/sla").then((r) => r.data),
    compliance: () => api.get<ComplianceSummary>("/dashboard/compliance-summary").then((r) => r.data),
    customer: () => api.get<CustomerMetrics>("/dashboard/customer").then((r) => r.data),
};
