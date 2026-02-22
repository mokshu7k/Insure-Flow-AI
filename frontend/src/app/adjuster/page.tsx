"use client";
import { useState, useRef, useEffect } from "react";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { adjusterService } from "@/services/adjusterService";
import { claimService } from "@/services/claimService";
import { MonoValue } from "@/components/ui";
import type { Claim, AdjusterChatResponse, AdjusterReportResponse } from "@/types";
import { Send, FileQuestion, Loader, Scale, PanelRightClose, PanelRightOpen, RefreshCw, Bot, User, ChevronDown, X } from "lucide-react";

interface Message { role: "user" | "ai"; content: string }

export default function AdjusterPage() {
    const [claims, setClaims] = useState<Claim[]>([]);
    const [selectedClaimId, setSelectedClaimId] = useState<string | undefined>();
    const [messages, setMessages] = useState<Message[]>([
        { role: "ai", content: "Hello. I'm the InsureFlow Adjuster Agent. Select a claim or ask a general question about claims, policies, or fraud patterns." }
    ]);
    const [input, setInput] = useState("");
    const [sending, setSending] = useState(false);
    const [report, setReport] = useState<AdjusterReportResponse | null>(null);
    const [reportLoading, setReportLoading] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [reportExpanded, setReportExpanded] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        claimService.list(1, 50).then((r) => setClaims(r.items)).catch(() => { });
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const send = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || sending) return;
        const text = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: text }]);
        setSending(true);
        try {
            const res: AdjusterChatResponse = await adjusterService.chat({ message: text, claim_id: selectedClaimId });
            setMessages((prev) => [...prev, { role: "ai", content: res.response }]);
        } catch {
            setMessages((prev) => [...prev, { role: "ai", content: "I encountered an error processing your request. Please try again." }]);
        } finally {
            setSending(false);
        }
    };

    const generateReport = async (force = false) => {
        if (!selectedClaimId) return;
        setReportLoading(true);
        try {
            const r = force
                ? await adjusterService.regenerateReport(selectedClaimId)
                : await adjusterService.generateReport(selectedClaimId);
            setReport(r);
            setReportExpanded(true);
        } catch {
            setMessages((prev) => [...prev, { role: "ai", content: "Failed to generate report. Please try again." }]);
        } finally {
            setReportLoading(false);
        }
    };

    const selectedClaim = claims.find((c) => c.id === selectedClaimId);

    return (
        <AuthGuard requireAdmin>
            <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <Scale size={16} color="var(--blue)" />
                    <span style={{ fontSize: "1rem", fontWeight: 600 }}>Adjuster Workstation</span>
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>— AI-powered claim intelligence</span>
                    <div style={{ marginLeft: "auto" }}>
                        <button
                            onClick={() => setSidebarOpen((o) => !o)}
                            className="btn btn-ghost"
                            title={sidebarOpen ? "Hide claims panel" : "Show claims panel"}
                            style={{ padding: "4px 8px" }}
                        >
                            {sidebarOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
                        </button>
                    </div>
                </div>
            }>
                <div style={{ display: "flex", height: "100%" }}>
                    {/* Claim selector sidebar — collapsible */}
                    {sidebarOpen && (
                        <div style={{
                            width: 280, flexShrink: 0,
                            borderRight: "1px solid var(--border)",
                            overflowY: "auto", padding: 16,
                            background: "var(--bg-base)",
                            transition: "width 200ms ease",
                        }}>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, marginBottom: 12 }}>
                                Select Claim
                            </div>
                            <div
                                onClick={() => setSelectedClaimId(undefined)}
                                style={{
                                    padding: "10px 12px", borderRadius: 6, cursor: "pointer", marginBottom: 8,
                                    background: !selectedClaimId ? "var(--blue-bg)" : "transparent",
                                    border: `1px solid ${!selectedClaimId ? "var(--blue-border)" : "var(--border)"}`,
                                    fontSize: "0.875rem", color: !selectedClaimId ? "var(--blue)" : "var(--text-secondary)",
                                    transition: "all 150ms",
                                }}
                            >
                                General query (no claim)
                            </div>
                            {claims.map((c) => (
                                <div
                                    key={c.id}
                                    onClick={() => setSelectedClaimId(c.id)}
                                    style={{
                                        padding: "10px 12px", borderRadius: 6, cursor: "pointer", marginBottom: 4,
                                        background: selectedClaimId === c.id ? "var(--bg-hover)" : "transparent",
                                        border: `1px solid ${selectedClaimId === c.id ? "var(--blue-border)" : "transparent"}`,
                                        transition: "all 150ms",
                                    }}
                                >
                                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 3 }}>
                                        {c.id.slice(0, 8)}…
                                    </div>
                                    <div style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{c.policy_number}</div>
                                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                                        {c.claim_type} · <span style={{ textTransform: "capitalize" }}>{c.status?.toLowerCase()}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Chat panel */}
                    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", minWidth: 0 }}>
                        {/* Actions bar */}
                        {selectedClaimId && (
                            <div style={{
                                padding: "10px 20px", borderBottom: "1px solid var(--border)",
                                display: "flex", gap: 10, alignItems: "center",
                                background: "var(--bg-panel)",
                            }}>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-muted)", flex: 1 }}>
                                    Claim: <strong style={{ color: "var(--text-secondary)" }}>{selectedClaimId.slice(0, 8)}…</strong>
                                    {selectedClaim && (
                                        <span style={{ marginLeft: 8, color: "var(--text-muted)" }}>
                                            · {selectedClaim.policy_number} · {selectedClaim.claim_type}
                                        </span>
                                    )}
                                </span>
                                <button className="btn btn-ghost" onClick={() => generateReport(false)} disabled={reportLoading} style={{ padding: "5px 12px", fontSize: "0.8125rem" }}>
                                    {reportLoading ? <Loader size={14} className="animate-spin" /> : <FileQuestion size={14} />}
                                    Generate Report
                                </button>
                                {report && (
                                    <button
                                        className="btn btn-ghost"
                                        onClick={() => generateReport(true)}
                                        disabled={reportLoading}
                                        title="Regenerate report from scratch"
                                        style={{ padding: "5px 10px", fontSize: "0.8125rem" }}
                                    >
                                        <RefreshCw size={13} className={reportLoading ? "animate-spin" : ""} />
                                    </button>
                                )}
                            </div>
                        )}

                        <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                            {messages.map((msg, i) => {
                                // Format content: ensure → markers are on new lines
                                const formatContent = (text: string) => {
                                    return text
                                        .split('\n')
                                        .map((line) => {
                                            const trimmed = line.trim();
                                            if (trimmed.startsWith('→')) {
                                                return trimmed;
                                            }
                                            return line;
                                        })
                                        .join('\n');
                                };
                                const formattedContent = formatContent(msg.content);
                                
                                return (
                                <div key={i} className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}>
                                    {msg.role === "ai" && (
                                        <div style={{ fontSize: "0.5625rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                                            Adjuster Agent
                                        </div>
                                    )}
                                    <div style={{ fontSize: "0.8125rem", lineHeight: 1.65, whiteSpace: "pre-wrap" }}>{formattedContent}</div>
                                </div>
                                );
                            })}
                            {sending && (
                                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                                    <div style={{
                                        width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                                        background: "var(--blue-bg)", border: "1px solid var(--blue-border)",
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                    }}>
                                        <Bot size={15} color="var(--blue)" />
                                    </div>
                                    <div style={{
                                        background: "var(--bg-surface)", border: "1px solid var(--border)",
                                        borderRadius: "6px 14px 14px 6px", padding: "12px 16px",
                                        display: "flex", gap: 8, alignItems: "center",
                                    }}>
                                        <Loader size={15} className="animate-spin" color="var(--text-muted)" />
                                        <span style={{ fontSize: "0.9375rem", color: "var(--text-muted)" }}>Thinking…</span>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Report preview — expandable */}
                        {report && (
                            <div style={{
                                maxHeight: reportExpanded ? "50vh" : 48,
                                overflowY: reportExpanded ? "auto" : "hidden",
                                margin: "0 20px 12px", borderRadius: 8,
                                background: "var(--bg-surface)", border: "1px solid var(--border)",
                                transition: "max-height 300ms ease",
                            }}>
                                <div
                                    onClick={() => setReportExpanded((e) => !e)}
                                    style={{
                                        display: "flex", justifyContent: "space-between", alignItems: "center",
                                        padding: "12px 16px", cursor: "pointer",
                                        position: "sticky", top: 0, background: "var(--bg-surface)", zIndex: 1,
                                        borderBottom: reportExpanded ? "1px solid var(--border)" : "none",
                                    }}
                                >
                                    <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-secondary)" }}>
                                        AI Claim Report
                                    </span>
                                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)" }}>
                                            {report.cached ? "cached" : "fresh"}
                                        </span>
                                        <ChevronDown size={14} color="var(--text-muted)" style={{
                                            transform: reportExpanded ? "rotate(180deg)" : "rotate(0deg)",
                                            transition: "transform 200ms",
                                        }} />
                                    </div>
                                </div>
                                {reportExpanded && (
                                    <pre style={{
                                        fontFamily: "var(--font-sans)", fontSize: "0.875rem", lineHeight: 1.8,
                                        whiteSpace: "pre-wrap", color: "var(--text-secondary)",
                                        padding: "16px 20px", margin: 0,
                                    }}>
                                        {report.report}
                                    </pre>
                                )}
                            </div>
                        )}

                        {/* Input */}
                        <form onSubmit={send} style={{
                            padding: "14px 24px", borderTop: "1px solid var(--border)",
                            display: "flex", gap: 10, background: "var(--bg-panel)",
                        }}>
                            <input
                                className="input"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder={selectedClaimId ? "Ask about this claim…" : "Ask anything about claims or fraud…"}
                                disabled={sending}
                                style={{ flex: 1, fontSize: "0.9375rem", padding: "10px 14px" }}
                            />
                            <button type="submit" className="btn btn-primary" disabled={!input.trim() || sending} style={{ padding: "10px 16px" }}>
                                <Send size={16} />
                            </button>
                        </form>
                    </div>
                </div>
            </CommandLayout>
        </AuthGuard>
    );
}
