import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: LucideIcon;
    trend?: { value: number; positive: boolean };
    className?: string;
    iconColor?: string;
}

export default function StatsCard({
    title,
    value,
    subtitle,
    icon: Icon,
    trend,
    className,
    iconColor = "text-indigo-500",
}: StatsCardProps) {
    return (
        <div
            className={cn(
                "bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 hover:shadow-lg transition-shadow duration-300 animate-fade-in",
                className
            )}
        >
            <div className="flex items-start justify-between">
                <div className="space-y-1">
                    <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
                        {title}
                    </p>
                    <p className="text-2xl font-bold text-[var(--color-card-foreground)]">
                        {value}
                    </p>
                    {subtitle && (
                        <p className="text-xs text-[var(--color-muted-foreground)]">
                            {subtitle}
                        </p>
                    )}
                    {trend && (
                        <p
                            className={cn(
                                "text-xs font-medium flex items-center gap-1",
                                trend.positive ? "text-emerald-500" : "text-red-500"
                            )}
                        >
                            <span>{trend.positive ? "↑" : "↓"}</span>
                            {Math.abs(trend.value)}%
                        </p>
                    )}
                </div>
                <div
                    className={cn(
                        "p-2.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/30",
                        iconColor
                    )}
                >
                    <Icon size={22} />
                </div>
            </div>
        </div>
    );
}
