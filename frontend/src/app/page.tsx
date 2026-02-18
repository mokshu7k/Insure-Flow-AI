"use client";

import Link from "next/link";
import {
  Shield,
  QrCode,
  Brain,
  ArrowRight,
  CheckCircle2,
  BarChart3,
  FileSearch,
  Zap,
} from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "AI Fraud Detection",
    desc: "Multi-agent explainable AI analyzing deterministic, statistical, and behavioral fraud patterns in real-time.",
    color: "from-indigo-500 to-purple-500",
  },
  {
    icon: QrCode,
    title: "Cashless QR Auth",
    desc: "HMAC-signed, time-limited, single-use QR tokens for secure cashless claim authorization.",
    color: "from-emerald-500 to-teal-500",
  },
  {
    icon: Shield,
    title: "Full Compliance",
    desc: "DPDP & HIPAA aligned — consent tracking, audit trails, data retention policies, and human-in-the-loop.",
    color: "from-amber-500 to-orange-500",
  },
  {
    icon: FileSearch,
    title: "OCR Processing",
    desc: "Automated document extraction with intelligent field parsing and confidence scoring.",
    color: "from-pink-500 to-rose-500",
  },
  {
    icon: BarChart3,
    title: "Analytics Dashboard",
    desc: "Real-time metrics, SLA tracking, fraud distribution heatmaps, and compliance health overview.",
    color: "from-cyan-500 to-blue-500",
  },
  {
    icon: Zap,
    title: "Smart Settlements",
    desc: "Automated settlement initiation with external payment gateway integration and status tracking.",
    color: "from-violet-500 to-fuchsia-500",
  },
];

const stats = [
  { value: "99.7%", label: "Uptime SLA" },
  { value: "<2s", label: "Fraud Analysis" },
  { value: "50K+", label: "Claims Processed" },
  { value: "DPDP", label: "Compliant" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 lg:px-12 h-16 border-b border-[var(--color-border)] bg-[var(--color-card)]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white text-sm">
            IF
          </div>
          <span className="font-bold text-lg">InsureFlow AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="px-4 py-2 text-sm font-medium text-[var(--color-foreground)] hover:text-[var(--color-primary)] transition-colors"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 rounded-lg transition-all shadow-md hover:shadow-lg"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/10 via-purple-600/5 to-transparent pointer-events-none" />
        <div className="absolute top-20 right-0 w-[500px] h-[500px] bg-gradient-to-l from-indigo-500/10 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-gradient-to-r from-purple-500/10 to-transparent rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-24 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-300 text-xs font-medium mb-6 animate-fade-in">
            <Zap size={14} />
            Powered by Explainable AI
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight animate-fade-in">
            Intelligent Insurance
            <br />
            <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Claim Intelligence
            </span>
          </h1>
          <p className="mt-6 text-lg text-[var(--color-muted-foreground)] max-w-2xl mx-auto animate-fade-in">
            AI-driven fraud detection, cashless QR authorization, and regulatory
            compliance — all in one platform built for the modern insurer.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4 animate-fade-in">
            <Link
              href="/register"
              className="flex items-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 rounded-xl transition-all shadow-lg hover:shadow-xl hover:scale-[1.02]"
            >
              Start Free Trial
              <ArrowRight size={16} />
            </Link>
            <Link
              href="/login"
              className="px-6 py-3 text-sm font-semibold text-[var(--color-foreground)] border border-[var(--color-border)] rounded-xl hover:bg-[var(--color-muted)] transition-colors"
            >
              Sign In
            </Link>
          </div>

          {/* Stats row */}
          <div className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-6 max-w-3xl mx-auto">
            {stats.map((s) => (
              <div key={s.label} className="text-center animate-fade-in">
                <p className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  {s.value}
                </p>
                <p className="text-xs text-[var(--color-muted-foreground)] mt-1">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold">Everything You Need</h2>
          <p className="text-[var(--color-muted-foreground)] mt-2">
            Enterprise-grade insurance intelligence, out of the box.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="group bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-6 hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            >
              <div
                className={`w-10 h-10 rounded-lg bg-gradient-to-br ${f.color} flex items-center justify-center mb-4`}
              >
                <f.icon size={20} className="text-white" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-[var(--color-muted-foreground)] leading-relaxed">
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust section */}
      <section className="border-t border-[var(--color-border)] py-16">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-2xl font-bold mb-8">Built for Trust</h2>
          <div className="grid sm:grid-cols-3 gap-6">
            {[
              "Human-in-the-loop enforcement",
              "Immutable audit trail",
              "Encrypted documents at rest",
              "Role-based access control",
              "DPDP right-to-erasure",
              "Explainable AI decisions",
            ].map((item) => (
              <div key={item} className="flex items-center gap-2 text-sm">
                <CheckCircle2
                  size={16}
                  className="text-emerald-500 shrink-0"
                />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] py-8 text-center text-sm text-[var(--color-muted-foreground)]">
        <p>© 2026 InsureFlow AI. Compliance-first insurance intelligence.</p>
      </footer>
    </div>
  );
}
