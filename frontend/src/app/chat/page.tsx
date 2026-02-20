"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CommandLayout } from "@/components/layout/CommandLayout";
import { agentService } from "@/services/agentService";
import { MessageSquare, Send, Loader2, Plus, Bot, User } from "lucide-react";

interface Message {
    role: "user" | "agent";
    content: string;
    timestamp: Date;
}

const STARTER_PROMPTS = [
    "How do I file a health claim?",
    "What documents do I need for a motor claim?",
    "Check the status of my latest claim",
    "How long does claim processing take?",
];

export default function ChatPage() {
    return (
        <AuthGuard>
            <ChatContent />
        </AuthGuard>
    );
}

function ChatContent() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);

    // Restore session id from localStorage on mount
    useEffect(() => {
        const sid = agentService.getSessionId();
        setSessionId(sid);
    }, []);

    // Scroll to latest message
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const sendMessage = useCallback(async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || loading) return;

        setInput("");
        setError(null);

        const userMsg: Message = { role: "user", content: trimmed, timestamp: new Date() };
        setMessages((prev) => [...prev, userMsg]);
        setLoading(true);

        try {
            const result = await agentService.sendMessage(trimmed, sessionId);
            setSessionId(result.session_id);
            setMessages((prev) => [
                ...prev,
                { role: "agent", content: result.reply, timestamp: new Date() },
            ]);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Something went wrong";
            setError(msg);
        } finally {
            setLoading(false);
        }
    }, [loading, sessionId]);

    function handleNewSession() {
        agentService.clearSession();
        setSessionId(null);
        setMessages([]);
        setError(null);
    }

    const isEmpty = messages.length === 0;

    return (
        <CommandLayout
            header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <MessageSquare size={15} color="var(--text-muted)" />
                    <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>Assistant</span>
                    {sessionId && (
                        <span style={{
                            fontFamily: "var(--font-mono)", fontSize: "0.6125rem",
                            color: "var(--text-muted)", background: "var(--bg-surface)",
                            border: "1px solid var(--border)", borderRadius: 3, padding: "1px 6px",
                        }}>
                            {sessionId.slice(0, 8)}
                        </span>
                    )}
                    <button
                        className="btn btn-ghost"
                        onClick={handleNewSession}
                        style={{ marginLeft: "auto", gap: 5, fontSize: "0.75rem" }}
                    >
                        <Plus size={12} /> New session
                    </button>
                </div>
            }
        >
            <div style={{
                display: "flex", flexDirection: "column",
                height: "calc(100vh - 49px)",
                maxWidth: 720, margin: "0 auto", width: "100%",
            }}>
                {/* Message Thread */}
                <div style={{ flex: 1, overflowY: "auto", padding: "20px 0" }}>
                    {isEmpty ? (
                        /* Empty state */
                        <div style={{ textAlign: "center", padding: "60px 20px" }}>
                            <div style={{
                                width: 52, height: 52, borderRadius: "50%",
                                background: "var(--blue-bg, rgba(59,130,246,0.1))",
                                border: "1px solid var(--blue-border, rgba(59,130,246,0.2))",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                margin: "0 auto 16px",
                            }}>
                                <Bot size={22} color="var(--blue)" />
                            </div>
                            <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>InsureFlow Assistant</h2>
                            <p style={{ color: "var(--text-muted)", fontSize: "0.8125rem", marginBottom: 28, maxWidth: 380, margin: "0 auto 28px" }}>
                                Ask me anything about your claims, policy, or the filing process.
                            </p>
                            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 400, margin: "0 auto" }}>
                                {STARTER_PROMPTS.map((p) => (
                                    <button
                                        key={p}
                                        className="btn btn-ghost"
                                        onClick={() => sendMessage(p)}
                                        style={{ justifyContent: "flex-start", textAlign: "left", fontSize: "0.8125rem" }}
                                    >
                                        {p}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        /* Messages */
                        <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "0 4px" }}>
                            {messages.map((msg, i) => (
                                <MessageBubble key={i} msg={msg} />
                            ))}
                            {loading && (
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <AgentAvatar />
                                    <div style={{
                                        background: "var(--bg-surface)", border: "1px solid var(--border)",
                                        borderRadius: "6px 12px 12px 6px", padding: "10px 14px",
                                        display: "flex", gap: 4, alignItems: "center",
                                    }}>
                                        <Loader2 size={13} style={{ animation: "spin 1s linear infinite", color: "var(--text-muted)" }} />
                                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Thinking…</span>
                                    </div>
                                </div>
                            )}
                            <div ref={bottomRef} />
                        </div>
                    )}
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        margin: "0 0 8px 0", padding: "8px 12px",
                        background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
                        borderRadius: 6, fontSize: "0.75rem", color: "var(--red, #ef4444)",
                    }}>
                        {error}
                    </div>
                )}

                {/* Input */}
                <div style={{
                    borderTop: "1px solid var(--border)", padding: "12px 0 16px",
                    display: "flex", gap: 8, alignItems: "flex-end",
                }}>
                    <textarea
                        className="input"
                        rows={1}
                        value={input}
                        onChange={(e) => {
                            setInput(e.target.value);
                            // Auto-resize
                            e.target.style.height = "auto";
                            e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                        }}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                sendMessage(input);
                            }
                        }}
                        placeholder="Ask about your claims… (Enter to send)"
                        disabled={loading}
                        style={{
                            flex: 1, resize: "none", overflowY: "hidden",
                            fontFamily: "inherit", lineHeight: 1.5,
                            minHeight: 38,
                        }}
                    />
                    <button
                        className="btn btn-primary"
                        disabled={!input.trim() || loading}
                        onClick={() => sendMessage(input)}
                        style={{ height: 38, padding: "0 14px", flexShrink: 0 }}
                    >
                        <Send size={14} />
                    </button>
                </div>
            </div>
        </CommandLayout>
    );
}

function AgentAvatar() {
    return (
        <div style={{
            width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
            background: "var(--blue-bg, rgba(59,130,246,0.1))",
            border: "1px solid var(--blue-border, rgba(59,130,246,0.2))",
            display: "flex", alignItems: "center", justifyContent: "center",
        }}>
            <Bot size={13} color="var(--blue)" />
        </div>
    );
}

function MessageBubble({ msg }: { msg: Message }) {
    const isUser = msg.role === "user";
    return (
        <div style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            flexDirection: isUser ? "row-reverse" : "row",
        }}>
            {/* Avatar */}
            {isUser ? (
                <div style={{
                    width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                    background: "var(--bg-surface)", border: "1px solid var(--border)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <User size={13} color="var(--text-muted)" />
                </div>
            ) : (
                <AgentAvatar />
            )}

            {/* Bubble */}
            <div style={{
                maxWidth: "72%",
                background: isUser ? "var(--blue)" : "var(--bg-surface)",
                color: isUser ? "#fff" : "var(--text-primary)",
                border: isUser ? "none" : "1px solid var(--border)",
                borderRadius: isUser ? "12px 6px 6px 12px" : "6px 12px 12px 6px",
                padding: "10px 14px",
                fontSize: "0.8125rem",
                lineHeight: 1.55,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
            }}>
                {msg.content}
                <div style={{
                    fontSize: "0.6rem",
                    color: isUser ? "rgba(255,255,255,0.6)" : "var(--text-muted)",
                    marginTop: 4,
                    textAlign: "right",
                }}>
                    {msg.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
            </div>
        </div>
    );
}
