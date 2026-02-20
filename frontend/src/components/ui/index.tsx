"use client";

// ── RiskBadge ──────────────────────────────────────────────
interface RiskBadgeProps { score: number | null }
export function RiskBadge({ score }: RiskBadgeProps) {
    if (score === null || score === undefined) return <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>—</span>;
    const pct = Math.round(score * 100);
    const cls = score >= 0.7 ? "risk-high" : score >= 0.4 ? "risk-medium" : "risk-low";
    return (
        <span className={`mono ${cls}`} style={{ fontSize: "0.8125rem", fontWeight: 600 }}>
            {pct.toString().padStart(3, "\u2007")}%
        </span>
    );
}

// ── StatusPill ─────────────────────────────────────────────
const STATUS_CLASS: Record<string, string> = {
    SUBMITTED: "pill-submitted", OCR_PROCESSED: "pill-submitted",
    UNDER_REVIEW: "pill-review", MANUAL_REVIEW_REQUIRED: "pill-review", FRAUD_ANALYZED: "pill-review",
    APPROVED: "pill-approved", PRE_AUTHORIZED: "pill-approved", SETTLED: "pill-settled",
    REJECTED: "pill-rejected",
    PENDING_REVIEW: "pill-review", ACCEPTED_BY_PATIENT: "pill-review",
};

interface StatusPillProps { status: string }
export function StatusPill({ status }: StatusPillProps) {
    const cls = STATUS_CLASS[status] || "pill-submitted";
    return <span className={`pill ${cls}`}>{status.replace(/_/g, " ")}</span>;
}

// ── MonoValue ──────────────────────────────────────────────
interface MonoValueProps { value: string | number | null | undefined; prefix?: string; muted?: boolean; size?: string }
export function MonoValue({ value, prefix = "", muted, size = "0.8125rem" }: MonoValueProps) {
    if (value === null || value === undefined) return <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: size }}>—</span>;
    return (
        <span className="mono" style={{ fontSize: size, color: muted ? "var(--text-muted)" : "var(--text-primary)" }}>
            {prefix}{value}
        </span>
    );
}

// ── StatCard ──────────────────────────────────────────────
interface StatCardProps { label: string; value: string | number | null; unit?: string; accent?: string; sub?: string }
export function StatCard({ label, value, unit, accent, sub }: StatCardProps) {
    return (
        <div className="stat-card">
            <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10, fontWeight: 500 }}>
                {label}
            </div>
            <div className="stat-value" style={{ color: accent || "var(--text-primary)", marginBottom: sub ? 6 : 0 }}>
                {value === null || value === undefined ? "—" : value}
                {unit && <span style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginLeft: 4, fontWeight: 400 }}>{unit}</span>}
            </div>
            {sub && <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{sub}</div>}
        </div>
    );
}

// ── FraudScoreBadge (large display) ───────────────────────
interface FraudScoreBadgeProps { score: number | null; label?: boolean }
export function FraudScoreBadge({ score, label }: FraudScoreBadgeProps) {
    if (score === null || score === undefined) return <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>N/A</span>;
    const pct = Math.round(score * 100);
    const color = score >= 0.7 ? "var(--crimson)" : score >= 0.4 ? "var(--amber)" : "var(--green)";
    const bgColor = score >= 0.7 ? "var(--crimson-bg)" : score >= 0.4 ? "var(--amber-bg)" : "var(--green-bg)";
    const borderColor = score >= 0.7 ? "var(--crimson-border)" : score >= 0.4 ? "var(--amber-border)" : "var(--green-border)";
    const riskLabel = score >= 0.7 ? "HIGH RISK" : score >= 0.4 ? "MEDIUM" : "LOW RISK";
    return (
        <div style={{
            display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 4,
            background: bgColor, border: `1px solid ${borderColor}`, borderRadius: 6, padding: "10px 18px"
        }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.75rem", fontWeight: 700, color, lineHeight: 1 }}>{pct}%</span>
            {label && <span style={{ fontSize: "0.5625rem", fontWeight: 600, letterSpacing: "0.1em", color, textTransform: "uppercase" }}>{riskLabel}</span>}
        </div>
    );
}

// ── Sparkline (inline SVG mini chart) ─────────────────────
interface SparklineProps { data: number[]; width?: number; height?: number; color?: string }
export function Sparkline({ data, width = 60, height = 20, color = "var(--blue)" }: SparklineProps) {
    if (!data || data.length < 2) return null;
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const pts = data.map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((v - min) / range) * height;
        return `${x},${y}`;
    }).join(" ");
    return (
        <svg width={width} height={height} style={{ overflow: "visible" }}>
            <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
        </svg>
    );
}
