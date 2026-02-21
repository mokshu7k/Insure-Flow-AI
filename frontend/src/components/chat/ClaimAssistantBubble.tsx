"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, X, Send, Loader2, Bot, Maximize2, ArrowRight } from "lucide-react";
import { agentService } from "@/services/agentService";

interface Message {
    role: "user" | "agent";
    content: string;
}

export function ClaimAssistantBubble() {
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Restore session id on mount
    useEffect(() => {
        setSessionId(agentService.getSessionId());
    }, []);

    // Auto-scroll
    useEffect(() => {
        if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, open]);

    const sendMessage = useCallback(async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || loading) return;
        setInput("");

        setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
        setLoading(true);
        try {
            let activeSessionId = sessionId;
            if (!activeSessionId) {
                activeSessionId = await agentService.createSession();
                setSessionId(activeSessionId);
                if (typeof window !== "undefined") {
                    localStorage.setItem("agent_session_id", activeSessionId);
                }
            }
            const result = await agentService.sendMessage(trimmed, activeSessionId);
            setSessionId(result.session_id);
            setMessages((prev) => [...prev, { role: "agent", content: result.reply }]);
        } catch {
            setMessages((prev) => [...prev, { role: "agent", content: "Sorry, something went wrong. Please try again." }]);
        } finally {
            setLoading(false);
        }
    }, [loading, sessionId]);

    return (
        <>
            {/* Panel */}
            {open && (
                <div style={{
                    position: "fixed", bottom: 76, right: 20, zIndex: 1000,
                    width: 380, height: 520,
                    background: "var(--bg-panel)", border: "1px solid var(--border)",
                    borderRadius: 12, boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
                    display: "flex", flexDirection: "column", overflow: "hidden",
                }}>
                    {/* Header */}
                    <div style={{
                        display: "flex", alignItems: "center", gap: 8, padding: "10px 14px",
                        borderBottom: "1px solid var(--border)",
                        background: "var(--bg-surface)",
                    }}>
                        <Bot size={15} color="var(--blue)" />
                        <span style={{ fontSize: "0.875rem", fontWeight: 600, flex: 1 }}>InsureFlow Assistant</span>
                        <button
                            title="Open full chat"
                            onClick={() => { setOpen(false); router.push("/chat"); }}
                            style={{ background: "none", border: "none", cursor: "pointer", padding: 2, color: "var(--text-muted)" }}
                        >
                            <Maximize2 size={13} />
                        </button>
                        <button
                            onClick={() => setOpen(false)}
                            style={{ background: "none", border: "none", cursor: "pointer", padding: 2, color: "var(--text-muted)" }}
                        >
                            <X size={13} />
                        </button>
                    </div>

                    {/* Messages */}
                    <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
                        {messages.length === 0 && (
                            <div style={{ textAlign: "center", padding: "24px 8px" }}>
                                <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", lineHeight: 1.5 }}>
                                    Hi! I can help with your claims, documents, or policy questions.
                                </p>
                                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 14 }}>
                                    {["File a new claim", "Check claim status", "Document requirements"].map((p) => (
                                        <button
                                            key={p}
                                            onClick={() => sendMessage(p)}
                                            style={{
                                                border: "1px solid var(--border)", borderRadius: 6,
                                                padding: "8px 12px", background: "var(--bg-surface)",
                                                cursor: "pointer", fontSize: "0.8125rem",
                                                color: "var(--text-secondary)", textAlign: "left",
                                            }}
                                        >
                                            {p} <ArrowRight size={10} style={{ marginLeft: 4 }} />
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
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
                            <div
                                key={i}
                                style={{
                                    alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                                    maxWidth: "85%",
                                    background: msg.role === "user" ? "var(--blue)" : "var(--bg-surface)",
                                    color: msg.role === "user" ? "#fff" : "var(--text-primary)",
                                    border: msg.role === "agent" ? "1px solid var(--border)" : "none",
                                    borderRadius: msg.role === "user" ? "12px 4px 4px 12px" : "4px 12px 12px 4px",
                                    padding: "8px 12px",
                                    fontSize: "0.875rem",
                                    lineHeight: 1.55,
                                    whiteSpace: "pre-wrap",
                                    wordBreak: "break-word",
                                }}
                            >
                                {formattedContent}
                            </div>
                            );
                        })}
                        {loading && (
                            <div style={{
                                alignSelf: "flex-start",
                                background: "var(--bg-surface)", border: "1px solid var(--border)",
                                borderRadius: "4px 12px 12px 4px", padding: "8px 12px",
                                display: "flex", gap: 6, alignItems: "center",
                            }}>
                                <Loader2 size={13} style={{ animation: "spin 1s linear infinite", color: "var(--text-muted)" }} />
                                <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Thinking…</span>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Input */}
                    <div style={{
                        borderTop: "1px solid var(--border)", padding: "10px 12px",
                        display: "flex", gap: 8,
                    }}>
                        <input
                            className="input"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    sendMessage(input);
                                }
                            }}
                            placeholder="Ask a question…"
                            disabled={loading}
                            style={{ flex: 1, height: 36, fontSize: "0.875rem", padding: "0 10px" }}
                        />
                        <button
                            className="btn btn-primary"
                            disabled={!input.trim() || loading}
                            onClick={() => sendMessage(input)}
                            style={{ height: 36, padding: "0 12px" }}
                        >
                            <Send size={14} />
                        </button>
                    </div>
                </div>
            )}

            {/* Toggle button */}
            <button
                onClick={() => setOpen((o) => !o)}
                style={{
                    position: "fixed", bottom: 20, right: 20, zIndex: 1001,
                    width: 48, height: 48, borderRadius: "50%",
                    background: open ? "var(--bg-surface)" : "var(--blue)",
                    border: open ? "1px solid var(--border)" : "none",
                    boxShadow: "0 4px 16px rgba(0,0,0,0.35)",
                    cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "all 200ms",
                    color: open ? "var(--text-primary)" : "#fff",
                }}
                title={open ? "Close assistant" : "Open assistant"}
            >
                {open ? <X size={18} /> : <MessageSquare size={18} />}
            </button>
        </>
    );
}
