"use client";

import { useEffect, useState } from "react";
import { userService } from "@/services/userService";
import type { User } from "@/types";
import { demoUsers } from "@/lib/demoData";
import { formatDate } from "@/lib/utils";
import { Loader2, Building2, CheckCircle2, XCircle } from "lucide-react";

export default function ProvidersPage() {
    const [providers, setProviders] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const data = await userService.list({ role: "PROVIDER", limit: 100 });
                setProviders(data);
            } catch {
                // DEMO MODE
                setProviders(demoUsers.filter(u => u.role === "PROVIDER"));
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Building2 size={24} className="text-indigo-500" />
                    Healthcare Providers
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Registered healthcare provider accounts
                </p>
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-48">
                    <Loader2 size={28} className="animate-spin text-indigo-500" />
                </div>
            ) : providers.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl">
                    <Building2 size={40} className="text-[var(--color-muted-foreground)] mb-2" />
                    <p className="text-sm text-[var(--color-muted-foreground)]">
                        No providers registered yet
                    </p>
                </div>
            ) : (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {providers.map((p) => (
                        <div
                            key={p.id}
                            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 hover:shadow-md transition-shadow animate-fade-in"
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white font-semibold">
                                    {p.email.charAt(0).toUpperCase()}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-sm truncate">{p.email}</p>
                                    <p className="text-xs text-[var(--color-muted-foreground)]">
                                        Joined {formatDate(p.created_at)}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <span
                                    className={`inline-flex items-center gap-1 text-xs font-medium ${p.is_active ? "text-emerald-500" : "text-red-500"
                                        }`}
                                >
                                    {p.is_active ? (
                                        <CheckCircle2 size={14} />
                                    ) : (
                                        <XCircle size={14} />
                                    )}
                                    {p.is_active ? "Active" : "Inactive"}
                                </span>
                                <span className="text-xs font-mono text-[var(--color-muted-foreground)] truncate max-w-[100px]">
                                    {p.id.slice(0, 8)}…
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
