interface FraudScoreGaugeProps {
    score: number | null;
    size?: number;
}

export default function FraudScoreGauge({
    score,
    size = 100,
}: FraudScoreGaugeProps) {
    if (score === null || score === undefined) {
        return (
            <div
                className="flex items-center justify-center rounded-full border-4 border-gray-200 dark:border-gray-700"
                style={{ width: size, height: size }}
            >
                <span className="text-xs text-[var(--color-muted-foreground)]">N/A</span>
            </div>
        );
    }

    const normalizedScore = Math.min(Math.max(score, 0), 1);
    const percentage = normalizedScore * 100;
    const radius = (size - 12) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference * (1 - normalizedScore);

    const getColor = (s: number) => {
        if (s < 0.3) return "#10b981";
        if (s < 0.6) return "#f59e0b";
        if (s < 0.8) return "#f97316";
        return "#ef4444";
    };

    const color = getColor(normalizedScore);

    return (
        <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={6}
                    className="text-gray-200 dark:text-gray-700"
                />
                {/* Score arc */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={color}
                    strokeWidth={6}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    className="transition-all duration-1000 ease-out"
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold" style={{ color }}>
                    {percentage.toFixed(0)}%
                </span>
                <span className="text-[10px] text-[var(--color-muted-foreground)]">
                    Risk
                </span>
            </div>
        </div>
    );
}
