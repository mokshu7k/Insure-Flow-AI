import { AlertTriangle } from "lucide-react";

interface FraudSignalsListProps {
    deterministic: string[];
    statistical: string[];
}

export default function FraudSignalsList({
    deterministic,
    statistical,
}: FraudSignalsListProps) {
    if (!deterministic.length && !statistical.length) {
        return (
            <p className="text-sm text-[var(--color-muted-foreground)]">
                No fraud signals detected.
            </p>
        );
    }

    return (
        <div className="space-y-4">
            {deterministic.length > 0 && (
                <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-red-500 mb-2 flex items-center gap-1.5">
                        <AlertTriangle size={14} />
                        Deterministic Signals
                    </h4>
                    <ul className="space-y-1.5">
                        {deterministic.map((signal, i) => (
                            <li
                                key={i}
                                className="text-sm px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-300 border border-red-100 dark:border-red-900/30"
                            >
                                {signal}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {statistical.length > 0 && (
                <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-500 mb-2 flex items-center gap-1.5">
                        <AlertTriangle size={14} />
                        Statistical Signals
                    </h4>
                    <ul className="space-y-1.5">
                        {statistical.map((signal, i) => (
                            <li
                                key={i}
                                className="text-sm px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-300 border border-amber-100 dark:border-amber-900/30"
                            >
                                {signal}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
