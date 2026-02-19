import { cn } from "@/lib/utils";
import type { ClaimStatus } from "@/types";

const statusConfig: Record<
    string,
    { label: string; bg: string; text: string; dot: string }
> = {
    SUBMITTED: {
        label: "Submitted",
        bg: "bg-blue-50 dark:bg-blue-950/30",
        text: "text-blue-700 dark:text-blue-300",
        dot: "bg-blue-500",
    },
    OCR_PROCESSED: {
        label: "Documents Processed",
        bg: "bg-cyan-50 dark:bg-cyan-950/30",
        text: "text-cyan-700 dark:text-cyan-300",
        dot: "bg-cyan-500",
    },
    UNDER_REVIEW: {
        label: "Under Review",
        bg: "bg-amber-50 dark:bg-amber-950/30",
        text: "text-amber-700 dark:text-amber-300",
        dot: "bg-amber-500",
    },
    FRAUD_ANALYZED: {
        label: "Analyzed",
        bg: "bg-indigo-50 dark:bg-indigo-950/30",
        text: "text-indigo-700 dark:text-indigo-300",
        dot: "bg-indigo-500",
    },
    APPROVED: {
        label: "Approved",
        bg: "bg-emerald-50 dark:bg-emerald-950/30",
        text: "text-emerald-700 dark:text-emerald-300",
        dot: "bg-emerald-500",
    },
    REJECTED: {
        label: "Rejected",
        bg: "bg-red-50 dark:bg-red-950/30",
        text: "text-red-700 dark:text-red-300",
        dot: "bg-red-500",
    },
    MANUAL_REVIEW_REQUIRED: {
        label: "Manual Review",
        bg: "bg-purple-50 dark:bg-purple-950/30",
        text: "text-purple-700 dark:text-purple-300",
        dot: "bg-purple-500",
    },
    SETTLED: {
        label: "Settled",
        bg: "bg-teal-50 dark:bg-teal-950/30",
        text: "text-teal-700 dark:text-teal-300",
        dot: "bg-teal-500",
    },
};

export default function ClaimStatusBadge({ status }: { status: ClaimStatus | string }) {
    const config = statusConfig[status] || {
        label: status,
        bg: "bg-gray-50 dark:bg-gray-900",
        text: "text-gray-700 dark:text-gray-300",
        dot: "bg-gray-500",
    };

    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
                config.bg,
                config.text
            )}
        >
            <span className={cn("w-1.5 h-1.5 rounded-full", config.dot)} />
            {config.label}
        </span>
    );
}
