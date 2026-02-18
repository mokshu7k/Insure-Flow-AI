import { cn } from "@/lib/utils";

interface ChartCardProps {
    title: string;
    subtitle?: string;
    children: React.ReactNode;
    className?: string;
    action?: React.ReactNode;
}

export default function ChartCard({
    title,
    subtitle,
    children,
    className,
    action,
}: ChartCardProps) {
    return (
        <div
            className={cn(
                "bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 animate-fade-in",
                className
            )}
        >
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="font-semibold text-[var(--color-card-foreground)]">
                        {title}
                    </h3>
                    {subtitle && (
                        <p className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
                            {subtitle}
                        </p>
                    )}
                </div>
                {action}
            </div>
            {children}
        </div>
    );
}
