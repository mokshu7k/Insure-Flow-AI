"use client";
import { useState, useEffect, useRef, useCallback, KeyboardEvent } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { CommandLayout } from "@/components/layout/CommandLayout";
import {
    agentService,
    ChatSessionSummary,
    ChatMessage as ApiChatMessage,
} from "@/services/agentService";
import { MessageSquare, Send, Loader2, Plus, Bot, User, Trash2, Check, X, Pencil, PanelLeftClose, PanelLeftOpen } from "lucide-react";

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

function timeAgo(iso: string | null): string {
    if (!iso) return "";
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

export default function ChatPage() {
    return (
        <AuthGuard>
            <ChatContent />
        </AuthGuard>
    );
}

function ChatContent() {
    const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [sessionsLoading, setSessionsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [renamingId, setRenamingId] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const bottomRef = useRef<HTMLDivElement>(null);
    const renameInputRef = useRef<HTMLInputElement>(null);

    // Load session list on mount
    const refreshSessions = useCallback(async () => {
        try {
            const list = await agentService.listSessions();
            setSessions(list);
        } catch {
            /* silently ignore */
        } finally {
            setSessionsLoading(false);
        }
    }, []);

    useEffect(() => {
        refreshSessions();
    }, [refreshSessions]);

    // Auto-scroll to latest message
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Focus rename input when editing
    useEffect(() => {
        if (renamingId) renameInputRef.current?.focus();
    }, [renamingId]);

    // Load a session's history when switching
    const loadSession = useCallback(async (sessionId: string) => {
        if (sessionId === activeSessionId) return;
        setActiveSessionId(sessionId);
        setMessages([]);
        setError(null);
        try {
            const detail = await agentService.getSession(sessionId);
            const mapped: Message[] = detail.messages.map((m: ApiChatMessage) => ({
                role: m.role === "ai" || m.role === "assistant" ? "agent" : "user",
                content: m.content,
                timestamp: new Date(),
            }));
            setMessages(mapped);
        } catch {
            setError("Could not load conversation history.");
        }
    }, [activeSessionId]);

    // Create a brand-new session
    const handleNewChat = useCallback(async () => {
        try {
            const sid = await agentService.createSession();
            await refreshSessions();
            setActiveSessionId(sid);
            setMessages([]);
            setError(null);
        } catch {
            setError("Could not create new session.");
        }
    }, [refreshSessions]);

    const sendMessage = useCallback(async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || loading) return;

        // Ensure an active session exists
        let sid = activeSessionId;
        if (!sid) {
            try {
                sid = await agentService.createSession();
                setActiveSessionId(sid);
            } catch {
                setError("Could not start a new session.");
                return;
            }
        }

        setInput("");
        setError(null);
        setMessages((prev) => [...prev, { role: "user", content: trimmed, timestamp: new Date() }]);
        setLoading(true);

        try {
            const result = await agentService.sendMessage(trimmed, sid);
            setMessages((prev) => [
                ...prev,
                { role: "agent", content: result.reply, timestamp: new Date() },
            ]);
            // Refresh sidebar (title may have been auto-generated)
            await refreshSessions();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Something went wrong.");
        } finally {
            setLoading(false);
        }
    }, [loading, activeSessionId, refreshSessions]);

    const handleDelete = useCallback(async (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        if (!confirm("Delete this conversation?")) return;
        try {
            await agentService.deleteSession(sessionId);
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
                setMessages([]);
            }
            await refreshSessions();
        } catch {
            /* silently ignore */
        }
    }, [activeSessionId, refreshSessions]);

    const startRename = useCallback((e: React.MouseEvent, session: ChatSessionSummary) => {
        e.stopPropagation();
        setRenamingId(session.session_id);
        setRenameValue(session.title);
    }, []);

    const commitRename = useCallback(async () => {
        if (!renamingId || !renameValue.trim()) {
            setRenamingId(null);
            return;
        }
        try {
            await agentService.renameSession(renamingId, renameValue.trim());
            await refreshSessions();
        } catch {
            /* ignore */
        } finally {
            setRenamingId(null);
        }
    }, [renamingId, renameValue, refreshSessions]);

    const handleRenameKey = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") commitRename();
        if (e.key === "Escape") setRenamingId(null);
    };

    const isEmpty = messages.length === 0;
    const [sidebarOpen, setSidebarOpen] = useState(true);

    return (
        <CommandLayout
            header={
                <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%" }}>
                    <MessageSquare size={16} color="var(--blue)" />
                    <span style={{ fontSize: "1rem", fontWeight: 600 }}>Assistant</span>
                    {activeSessionId && (
                        <span style={{
                            fontFamily: "var(--font-mono)", fontSize: "0.6875rem",
                            color: "var(--text-muted)", background: "var(--bg-surface)",
                            border: "1px solid var(--border)", borderRadius: 3, padding: "2px 8px",
                        }}>
                            {activeSessionId.slice(0, 8)}
                        </span>
                    )}
                    <div style={{ marginLeft: "auto" }}>
                        <button
                            onClick={() => setSidebarOpen((o) => !o)}
                            className="btn btn-ghost"
                            title={sidebarOpen ? "Hide sessions" : "Show sessions"}
                            style={{ padding: "4px 8px" }}
                        >
                            {sidebarOpen ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
                        </button>
                    </div>
                </div>
            }
        >
            {/* Two-column layout inside the page */}
            <div style={{ display: "flex", height: "calc(100vh - 52px)" }}>

                {/* â”€â”€â”€ Sidebar â”€â”€â”€ */}
                {sidebarOpen && (<aside style={{
                    width: 260, flexShrink: 0,
                    borderRight: "1px solid var(--border)",
                    display: "flex", flexDirection: "column",
                    background: "var(--bg-base)",
                    overflowY: "auto",
                    transition: "width 200ms ease",
                }}>
                    {/* New chat button */}
                    <div style={{ padding: "12px 10px 8px" }}>
                        <button
                            className="btn btn-primary"
                            onClick={handleNewChat}
                            style={{ width: "100%", gap: 6, fontSize: "0.875rem", padding: "8px 14px" }}
                        >
                            <Plus size={14} /> New chat
                        </button>
                    </div>

                    {/* Session list */}
                    <div style={{ flex: 1, overflowY: "auto", padding: "4px 6px" }}>
                        {sessionsLoading ? (
                            <div style={{ padding: "20px 0", textAlign: "center" }}>
                                <Loader2 size={14} style={{ animation: "spin 1s linear infinite", color: "var(--text-muted)" }} />
                            </div>
                        ) : sessions.length === 0 ? (
                            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "16px 8px", textAlign: "center" }}>
                                No conversations yet
                            </p>
                        ) : (
                            sessions.map((s) => (
                                <SessionItem
                                    key={s.session_id}
                                    session={s}
                                    isActive={s.session_id === activeSessionId}
                                    isRenaming={renamingId === s.session_id}
                                    renameValue={renameValue}
                                    renameInputRef={renameInputRef}
                                    onSelect={() => loadSession(s.session_id)}
                                    onDelete={(e) => handleDelete(e, s.session_id)}
                                    onStartRename={(e) => startRename(e, s)}
                                    onRenameChange={setRenameValue}
                                    onRenameKey={handleRenameKey}
                                    onRenameBlur={commitRename}
                                    onRenameCancel={() => setRenamingId(null)}
                                />
                            ))
                        )}
                    </div>
                </aside>)}

                {/* Chat panel */}
                <div style={{
                    flex: 1, display: "flex", flexDirection: "column",
                    maxWidth: 800, margin: "0 auto", width: "100%",
                    padding: "0 24px", minWidth: 0,
                }}>
                    {/* Message thread */}
                    <div style={{ flex: 1, overflowY: "auto", padding: "24px 0" }}>
                        {isEmpty ? (
                            <div style={{ textAlign: "center", padding: "60px 20px" }}>
                                <div style={{
                                    width: 56, height: 56, borderRadius: "50%",
                                    background: "var(--blue-bg, rgba(59,130,246,0.1))",
                                    border: "1px solid var(--blue-border, rgba(59,130,246,0.2))",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    margin: "0 auto 16px",
                                }}>
                                    <Bot size={24} color="var(--blue)" />
                                </div>
                                <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: 8 }}>InsureFlow Assistant</h2>
                                <p style={{ color: "var(--text-muted)", fontSize: "0.9375rem", marginBottom: 32, maxWidth: 420, margin: "0 auto 32px" }}>
                                    Ask me anything about your claims, policy, or the filing process.
                                </p>
                                <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420, margin: "0 auto" }}>
                                    {STARTER_PROMPTS.map((p) => (
                                        <button
                                            key={p}
                                            className="btn btn-ghost"
                                            onClick={() => sendMessage(p)}
                                            style={{ justifyContent: "flex-start", textAlign: "left", fontSize: "0.9375rem", padding: "10px 14px" }}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: 18, padding: "0 4px" }}>
                                {messages.map((msg, i) => (
                                    <MessageBubble key={i} msg={msg} />
                                ))}
                                {loading && (
                                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                        <AgentAvatar />
                                        <div style={{
                                            background: "var(--bg-surface)", border: "1px solid var(--border)",
                                            borderRadius: "6px 14px 14px 6px", padding: "12px 16px",
                                            display: "flex", gap: 6, alignItems: "center",
                                        }}>
                                            <Loader2 size={15} className="animate-spin" style={{ color: "var(--text-muted)" }} />
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
                            margin: "0 0 8px 0", padding: "10px 14px",
                            background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
                            borderRadius: 6, fontSize: "0.8125rem", color: "var(--red, #ef4444)",
                        }}>
                            {error}
                        </div>
                    )}

                    {/* Input */}
                    <div style={{
                        borderTop: "1px solid var(--border)", padding: "14px 0 18px",
                        display: "flex", gap: 10, alignItems: "flex-end",
                    }}>
                        <textarea
                            className="input"
                            rows={1}
                            value={input}
                            onChange={(e) => {
                                setInput(e.target.value);
                                e.target.style.height = "auto";
                                e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
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
                                minHeight: 42, fontSize: "0.9375rem",
                                padding: "10px 14px",
                            }}
                        />
                        <button
                            className="btn btn-primary"
                            disabled={!input.trim() || loading}
                            onClick={() => sendMessage(input)}
                            style={{ height: 42, padding: "0 16px", flexShrink: 0 }}
                        >
                            <Send size={16} />
                        </button>
                    </div>
                </div>
            </div>
        </CommandLayout>
    );
}

// â”€â”€ SessionItem â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
interface SessionItemProps {
    session: ChatSessionSummary;
    isActive: boolean;
    isRenaming: boolean;
    renameValue: string;
    renameInputRef: React.RefObject<HTMLInputElement | null>;
    onSelect: () => void;
    onDelete: (e: React.MouseEvent) => void;
    onStartRename: (e: React.MouseEvent) => void;
    onRenameChange: (v: string) => void;
    onRenameKey: (e: KeyboardEvent<HTMLInputElement>) => void;
    onRenameBlur: () => void;
    onRenameCancel: () => void;
}

function SessionItem({
    session, isActive, isRenaming, renameValue, renameInputRef,
    onSelect, onDelete, onStartRename, onRenameChange, onRenameKey, onRenameBlur, onRenameCancel,
}: SessionItemProps) {
    const [hovered, setHovered] = useState(false);

    return (
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onClick={isRenaming ? undefined : onSelect}
            style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 10px", borderRadius: 6,
                background: isActive ? "var(--bg-surface)" : hovered ? "var(--bg-hover)" : "transparent",
                border: isActive ? "1px solid var(--border)" : "1px solid transparent",
                cursor: "pointer", marginBottom: 2,
                transition: "background 150ms",
            }}
        >
            {isRenaming ? (
                <div style={{ flex: 1, display: "flex", gap: 4, alignItems: "center" }} onClick={(e) => e.stopPropagation()}>
                    <input
                        ref={renameInputRef}
                        value={renameValue}
                        onChange={(e) => onRenameChange(e.target.value)}
                        onKeyDown={onRenameKey}
                        onBlur={onRenameBlur}
                        style={{
                            flex: 1, fontSize: "0.8125rem", background: "var(--bg-base)",
                            border: "1px solid var(--blue)", borderRadius: 4,
                            padding: "3px 8px", color: "var(--text-primary)", outline: "none",
                        }}
                    />
                    <button
                        className="btn btn-ghost"
                        onClick={onRenameBlur}
                        style={{ padding: "2px 4px", minWidth: 0, height: "auto" }}
                        title="Save"
                    >
                        <Check size={11} />
                    </button>
                    <button
                        className="btn btn-ghost"
                        onClick={(e) => { e.stopPropagation(); onRenameCancel(); }}
                        style={{ padding: "2px 4px", minWidth: 0, height: "auto" }}
                        title="Cancel"
                    >
                        <X size={11} />
                    </button>
                </div>
            ) : (
                <>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                            fontSize: "0.8125rem", fontWeight: isActive ? 600 : 400,
                            color: "var(--text-primary)",
                            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                        }}>
                            {session.title}
                        </div>
                        <div style={{ fontSize: "0.6875rem", color: "var(--text-muted)", marginTop: 2 }}>
                            {timeAgo(session.updated_at)}
                        </div>
                    </div>
                    {(hovered || isActive) && (
                        <div style={{ display: "flex", gap: 2, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                            <button
                                className="btn btn-ghost"
                                onClick={onStartRename}
                                title="Rename"
                                style={{ padding: "3px 4px", minWidth: 0, height: "auto" }}
                            >
                                <Pencil size={11} />
                            </button>
                            <button
                                className="btn btn-ghost"
                                onClick={onDelete}
                                title="Delete"
                                style={{ padding: "3px 4px", minWidth: 0, height: "auto", color: "var(--red, #ef4444)" }}
                            >
                                <Trash2 size={11} />
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// â”€â”€ Shared sub-components â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function AgentAvatar() {
    return (
        <div style={{
            width: 34, height: 34, borderRadius: "50%", flexShrink: 0,
            background: "var(--blue-bg, rgba(59,130,246,0.1))",
            border: "1px solid var(--blue-border, rgba(59,130,246,0.2))",
            display: "flex", alignItems: "center", justifyContent: "center",
        }}>
            <Bot size={16} color="var(--blue)" />
        </div>
    );
}

function renderAgentContent(content: string): React.ReactNode {
    // Normalise: move inline → bullets onto their own lines, split concatenated sentences
    const normalized = content
        .replace(/([^\n])→\s*/g, "$1\n→ ")       // "text→ item" → "text\n→ item"
        .replace(/\.\s*([A-Z][a-z])/g, ".\n$1")  // ".Next sentence" → ".\nNext sentence"
        .trim();

    const lines = normalized.split("\n").filter((l) => l.trim() !== "");

    const nodes: React.ReactNode[] = [];
    let bullets: string[] = [];

    const flushBullets = (key: string) => {
        if (!bullets.length) return;
        const captured = bullets.slice();
        bullets = [];
        nodes.push(
            <ul key={key} style={{ margin: "8px 0 0", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                {captured.map((item, i) => (
                    <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                        <span style={{ color: "var(--blue)", flexShrink: 0, lineHeight: 1.65 }}>→</span>
                        <span style={{ lineHeight: 1.65 }}>{item}</span>
                    </li>
                ))}
            </ul>
        );
    };

    lines.forEach((line, i) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("→")) {
            bullets.push(trimmed.replace(/^→\s*/, ""));
        } else {
            flushBullets(`ul-${i}`);
            nodes.push(
                <p key={`p-${i}`} style={{ margin: nodes.length > 0 ? "6px 0 0" : "0", lineHeight: 1.65 }}>
                    {trimmed}
                </p>
            );
        }
    });
    flushBullets("ul-end");

    return <>{nodes}</>;
}

function MessageBubble({ msg }: { msg: Message }) {
    const isUser = msg.role === "user";

    return (
        <div style={{
            display: "flex", alignItems: "flex-start", gap: 10,
            flexDirection: isUser ? "row-reverse" : "row",
        }}>
            {isUser ? (
                <div style={{
                    width: 34, height: 34, borderRadius: "50%", flexShrink: 0,
                    background: "var(--bg-surface)", border: "1px solid var(--border)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                    <User size={15} color="var(--text-muted)" />
                </div>
            ) : (
                <AgentAvatar />
            )}
            <div style={{
                maxWidth: "75%",
                background: isUser ? "var(--blue)" : "var(--bg-surface)",
                color: isUser ? "#fff" : "var(--text-primary)",
                border: isUser ? "none" : "1px solid var(--border)",
                borderRadius: isUser ? "14px 6px 6px 14px" : "6px 14px 14px 6px",
                padding: "12px 16px",
                fontSize: "0.9375rem",
                wordBreak: "break-word",
            }}>
                {isUser
                    ? <span style={{ whiteSpace: "pre-wrap", lineHeight: 1.65 }}>{msg.content}</span>
                    : renderAgentContent(msg.content)
                }
                <div style={{
                    fontSize: "0.6875rem",
                    color: isUser ? "rgba(255,255,255,0.6)" : "var(--text-muted)",
                    marginTop: 6, textAlign: "right",
                }}>
                    {msg.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
            </div>
        </div>
    );
}
