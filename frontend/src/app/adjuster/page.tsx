"use client";
import { useState, useRef, useEffect } from "react";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { adjusterService } from "@/services/adjusterService";
import { claimService } from "@/services/claimService";
import { MonoValue } from "@/components/ui";
import type { Claim, AdjusterChatResponse, AdjusterReportResponse } from "@/types";
import { Send, FileQuestion, Download, Loader, Scale } from "lucide-react";

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

    const generateReport = async () => {
        if (!selectedClaimId) return;
        setReportLoading(true);
        try {
            const r = await adjusterService.generateReport(selectedClaimId);
            setReport(r);
        } catch {
            setMessages((prev) => [...prev, { role: "ai", content: "Failed to generate report. Please try again." }]);
        } finally {
            setReportLoading(false);
        }
    };

    return (
        <AuthGuard requireAdmin>
            <CommandLayout header={
                <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                    <Scale size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Adjuster Workstation</span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>— AI-powered claim intelligence</span>
                </div>
            }>
                <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", height: "100%" }}>
                    {/* Claim selector */}
                    <div style={{ borderRight: "1px solid var(--border)", overflowY: "auto", padding: 16 }}>
                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, marginBottom: 10 }}>
                            Select Claim
                        </div>
                        <div
                            onClick={() => setSelectedClaimId(undefined)}
                            style={{
                                padding: "8px 10px", borderRadius: 4, cursor: "pointer", marginBottom: 6,
                                background: !selectedClaimId ? "var(--blue-bg)" : "transparent",
                                border: `1px solid ${!selectedClaimId ? "var(--blue-border)" : "transparent"}`,
                                fontSize: "0.8125rem", color: !selectedClaimId ? "var(--blue)" : "var(--text-secondary)",
                            }}
                        >
                            General query (no claim)
                        </div>
                        {claims.map((c) => (
                            <div
                                key={c.id}
                                onClick={() => setSelectedClaimId(c.id)}
                                style={{
                                    padding: "8px 10px", borderRadius: 4, cursor: "pointer", marginBottom: 4,
                                    background: selectedClaimId === c.id ? "var(--bg-hover)" : "transparent",
                                    border: `1px solid ${selectedClaimId === c.id ? "var(--border-strong)" : "transparent"}`,
                                }}
                            >
                                <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", marginBottom: 2 }}>
                                    {c.id.slice(0, 8)}…
                                </div>
                                <div style={{ fontSize: "0.75rem", fontWeight: 500 }}>{c.policy_number}</div>
                                <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)" }}>{c.claim_type} · {c.status}</div>
                            </div>
                        ))}
                    </div>

                    {/* Chat panel */}
                    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
                        {/* Actions bar */}
                        {selectedClaimId && (
                            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center" }}>
                                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", color: "var(--text-muted)", flex: 1 }}>
                                    Claim: {selectedClaimId.slice(0, 8)}…
                                </span>
                                <button className="btn btn-ghost" onClick={generateReport} disabled={reportLoading} style={{ padding: "4px 10px" }}>
                                    {reportLoading ? <Loader size={13} /> : <FileQuestion size={13} />}
                                    Generate report
                                </button>
                            </div>
                        )}

                        {/* Messages */}
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
                                <div className="chat-bubble-ai" style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                    <Loader size={13} style={{ animation: "spin 1s linear infinite" }} />
                                    <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Thinking…</span>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Report preview */}
                        {report && (
                            <div style={{ maxHeight: 300, overflowY: "auto", margin: "0 20px 16px", borderRadius: 4, background: "var(--bg-surface)", border: "1px solid var(--border)", padding: 16 }}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                                    <span style={{ fontSize: "0.6875rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>Adjuster Report</span>
                                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-muted)" }}>
                                        {new Date(report.generated_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false })}
                                    </span>
                                </div>
                                <pre style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", lineHeight: 1.7, whiteSpace: "pre-wrap", color: "var(--text-secondary)" }}>
                                    {report.report}
                                </pre>
                            </div>
                        )}

                        {/* Input */}
                        <form onSubmit={send} style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", gap: 10 }}>
                            <input
                                className="input"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder={selectedClaimId ? "Ask about this claim…" : "Ask anything about claims or fraud…"}
                                disabled={sending}
                                style={{ flex: 1 }}
                            />
                            <button type="submit" className="btn btn-primary" disabled={!input.trim() || sending} style={{ padding: "8px 14px" }}>
                                <Send size={14} />
                            </button>
                        </form>
                    </div>
                </div>
            </CommandLayout>
        </AuthGuard>
    );
}
