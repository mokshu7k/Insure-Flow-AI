"use client";
import Link from "next/link";
import {
  Shield, Brain, FileSearch, BarChart3, Zap, CheckCircle,
  ArrowRight, AlertTriangle, Users, Lock, FileText
} from "lucide-react";
import { Navbar } from "@/components/layout/PublicLayout";

const FEATURES = [
  {
    icon: Brain,
    title: "3-Layer Fraud Engine",
    desc: "Deterministic rules → Statistical anomaly detection (z-score) → Gemini AI narrative. Six independent signals, one explainable score.",
    accent: "var(--crimson)",
    bg: "var(--crimson-bg)",
    border: "var(--crimson-border)",
  },
  {
    icon: FileSearch,
    title: "Tesseract OCR Pipeline",
    desc: "Automated document ingestion: preprocess → extract → parse. Supports invoices, prescriptions, discharge summaries, police reports.",
    accent: "var(--blue)",
    bg: "var(--blue-bg)",
    border: "var(--blue-border)",
  },
  {
    icon: Shield,
    title: "DPDP / HIPAA Compliance",
    desc: "Consent enforcement, immutable audit trails, right-to-erasure, PII sanitization with configurable privacy modes.",
    accent: "var(--green)",
    bg: "var(--green-bg)",
    border: "var(--green-border)",
  },
  {
    icon: Lock,
    title: "Human-in-the-Loop",
    desc: "Admin must manually approve or reject any claim. No automated settlement without explicit human decision. Full transparency.",
    accent: "var(--amber)",
    bg: "var(--amber-bg)",
    border: "var(--amber-border)",
  },
  {
    icon: BarChart3,
    title: "Analytics Command Center",
    desc: "Real-time fraud distribution, SLA heatmaps, claim status breakdown, compliance health — all from live backend APIs.",
    accent: "var(--blue)",
    bg: "var(--blue-bg)",
    border: "var(--blue-border)",
  },
  {
    icon: Zap,
    title: "Adjuster AI Agent",
    desc: "Ask questions about any claim in plain English. Get structured fraud summaries, flag explanations, and recommendation reports.",
    accent: "var(--amber)",
    bg: "var(--amber-bg)",
    border: "var(--amber-border)",
  },
];

const ROLES = [
  {
    role: "CUSTOMER",
    label: "Policyholder",
    icon: Users,
    color: "var(--blue)",
    border: "var(--blue-border)",
    bg: "var(--blue-bg)",
    capabilities: [
      "Submit claims with documents",
      "Track claim status in real-time",
      "Upload OCR-processed invoices",
      "Consent management (DPDP)",
    ],
    cta: "/register",
    ctaLabel: "Register as Customer",
  },
  {
    role: "PROVIDER",
    label: "Healthcare Provider",
    icon: FileText,
    color: "var(--green)",
    border: "var(--green-border)",
    bg: "var(--green-bg)",
    capabilities: [
      "View claims related to your facility",
      "Upload supporting medical documents",
      "Track settlement status",
      "Access discharge summaries",
    ],
    cta: "/register",
    ctaLabel: "Register as Provider",
  },
  {
    role: "INSURER_ADMIN",
    label: "Insurer Admin",
    icon: Brain,
    color: "var(--crimson)",
    border: "var(--crimson-border)",
    bg: "var(--crimson-bg)",
    capabilities: [
      "Trigger 3-layer fraud analysis",
      "Approve, reject, or flag claims",
      "Full operations dashboard",
      "Adjuster AI agent access",
    ],
    cta: "/login",
    ctaLabel: "Admin Sign In",
  },
  {
    role: "AUDITOR",
    label: "Compliance Auditor",
    icon: Shield,
    color: "var(--amber)",
    border: "var(--amber-border)",
    bg: "var(--amber-bg)",
    capabilities: [
      "Full immutable audit trail",
      "Compliance metrics & reports",
      "Consent history per user",
      "Fraud assessment history",
    ],
    cta: "/login",
    ctaLabel: "Auditor Sign In",
  },
];

const TRUST_ITEMS = [
  "Human-in-the-loop enforcement — no auto-settlement",
  "Immutable audit trail on every action",
  "Fernet-encrypted documents at rest",
  "Role-based access control (4 roles)",
  "DPDP right-to-erasure implementation",
  "Explainable AI — every score has a reason",
  "PII sanitization before AI processing",
  "Config-versioned fraud assessments",
];

const STATS = [
  { value: "3-Layer", label: "Fraud detection layers", color: "var(--crimson)" },
  { value: "L1+L2+L3", label: "Rules + Stats + AI", color: "var(--amber)" },
  { value: "DPDP", label: "Compliant by design", color: "var(--green)" },
  { value: "4", label: "Role-gated portals", color: "var(--blue)" },
];

export default function HomePage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-base)", fontFamily: "var(--font-sans)" }}>
      <Navbar />

      {/* Hero */}
      <section style={{ maxWidth: 860, margin: "0 auto", padding: "80px 32px 60px", textAlign: "center" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          border: "1px solid var(--crimson-border)", background: "var(--crimson-bg)",
          borderRadius: 20, padding: "4px 14px", marginBottom: 24,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--crimson)", display: "inline-block" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--crimson)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            AI-powered · human-gated
          </span>
        </div>
        <h1 style={{ fontSize: "clamp(2rem, 5vw, 3.25rem)", fontWeight: 800, lineHeight: 1.1, marginBottom: 20, letterSpacing: "-0.02em" }}>
          Insurance Claims<br />
          <span style={{ color: "var(--blue)" }}>Intelligence Platform</span>
        </h1>
        <p style={{ fontSize: "1rem", color: "var(--text-secondary)", lineHeight: 1.75, maxWidth: 560, margin: "0 auto 36px" }}>
          End-to-end claims processing with explainable AI fraud detection,
          OCR document processing, and compliance built for DPDP &amp; HIPAA.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/register" style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 24px", background: "var(--blue)", color: "#fff",
            textDecoration: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.875rem",
          }}>
            Start free trial <ArrowRight size={15} />
          </Link>
          <Link href="/login" style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 24px", border: "1px solid var(--border)", color: "var(--text-primary)",
            textDecoration: "none", borderRadius: 6, fontSize: "0.875rem",
          }}>
            Sign in to dashboard
          </Link>
        </div>

        {/* Stats row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 56 }}>
          {STATS.map((s) => (
            <div key={s.label} style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 6, padding: "16px 12px", textAlign: "center" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.25rem", fontWeight: 700, color: s.color, marginBottom: 4 }}>{s.value}</div>
              <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features grid */}
      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "20px 32px 64px" }}>
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Platform capabilities</div>
          <h2 style={{ fontSize: "1.625rem", fontWeight: 700 }}>Everything the modern insurer needs</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
          {FEATURES.map((f) => (
            <div key={f.title} style={{ background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, padding: "20px 22px" }}>
              <div style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                width: 36, height: 36, borderRadius: 6,
                background: f.bg, border: `1px solid ${f.border}`,
                marginBottom: 14,
              }}>
                <f.icon size={17} color={f.accent} />
              </div>
              <div style={{ fontWeight: 600, fontSize: "0.9375rem", marginBottom: 8 }}>{f.title}</div>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.65 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Role Portals */}
      <section style={{ borderTop: "1px solid var(--border)", padding: "64px 32px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Role-gated access</div>
            <h2 style={{ fontSize: "1.625rem", fontWeight: 700 }}>Four portals, one platform</h2>
            <p style={{ color: "var(--text-muted)", marginTop: 8, fontSize: "0.875rem" }}>Different capabilities based on who you are</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {ROLES.map((r) => (
              <div key={r.role} style={{ background: "var(--bg-panel)", border: `1px solid var(--border)`, borderRadius: 8, padding: "22px 20px", display: "flex", flexDirection: "column" }}>
                <div style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  width: 36, height: 36, borderRadius: 6,
                  background: r.bg, border: `1px solid ${r.border}`,
                  marginBottom: 14,
                }}>
                  <r.icon size={17} color={r.color} />
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: r.color, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>{r.role}</div>
                <div style={{ fontWeight: 600, fontSize: "0.9375rem", marginBottom: 14 }}>{r.label}</div>
                <ul style={{ flex: 1, listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                  {r.capabilities.map((c) => (
                    <li key={c} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                      <CheckCircle size={13} color="var(--green)" style={{ marginTop: 2, flexShrink: 0 }} />
                      {c}
                    </li>
                  ))}
                </ul>
                <Link href={r.cta} style={{
                  display: "block", marginTop: 20, textAlign: "center",
                  padding: "8px 16px", fontSize: "0.8125rem", fontWeight: 500,
                  background: r.bg, border: `1px solid ${r.border}`, color: r.color,
                  textDecoration: "none", borderRadius: 4,
                }}>
                  {r.ctaLabel}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trust checklist */}
      <section style={{ borderTop: "1px solid var(--border)", padding: "60px 32px" }}>
        <div style={{ maxWidth: 860, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 36 }}>
            <h2 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Built for regulated environments</h2>
            <p style={{ color: "var(--text-muted)", marginTop: 8, fontSize: "0.875rem" }}>Compliance, privacy, and auditability are first-class concerns — not afterthoughts.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "10px 32px" }}>
            {TRUST_ITEMS.map((item) => (
              <div key={item} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                <CheckCircle size={14} color="var(--green)" style={{ flexShrink: 0 }} />
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section style={{ borderTop: "1px solid var(--border)", padding: "56px 32px", textAlign: "center" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: 12 }}>Ready to process smarter claims?</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: 28, fontSize: "0.875rem" }}>Register for your portal or sign in if you already have an account.</p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <Link href="/register" style={{ padding: "10px 24px", background: "var(--blue)", color: "#fff", textDecoration: "none", borderRadius: 6, fontWeight: 600, fontSize: "0.875rem" }}>
            Create account
          </Link>
          <Link href="/login" style={{ padding: "10px 24px", border: "1px solid var(--border)", color: "var(--text-primary)", textDecoration: "none", borderRadius: 6, fontSize: "0.875rem" }}>
            Sign in
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid var(--border)", padding: "24px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle size={14} color="var(--amber)" />
          <span style={{ fontWeight: 600, fontSize: "0.8125rem" }}>InsureFlow</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>Claim Intelligence Platform</span>
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
          © 2026 · DPDP &amp; HIPAA compliant · Made for Techfiesta 2026
        </span>
      </footer>
    </div>
  );
}
