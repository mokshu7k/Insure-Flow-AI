"use client";

import { useEffect, useState } from "react";
import { userService } from "@/services/userService";
import type { User, UserRole } from "@/types";
import { demoUsers } from "@/lib/demoData";
import { formatDate } from "@/lib/utils";
import { Loader2, Users, Shield, CheckCircle2, XCircle } from "lucide-react";

const roleColors: Record<string, string> = {
    CUSTOMER: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300",
    PROVIDER:
        "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300",
    INSURER_ADMIN:
        "bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300",
    AUDITOR:
        "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300",
};

const roleFilters: (UserRole | "ALL")[] = [
    "ALL",
    "CUSTOMER",
    "PROVIDER",
    "INSURER_ADMIN",
    "AUDITOR",
];

export default function UsersPage() {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [roleFilter, setRoleFilter] = useState<string>("ALL");
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const data = await userService.list({
                    role: roleFilter === "ALL" ? undefined : roleFilter,
                    limit: 100,
                });
                setUsers(data);
            } catch {
                // DEMO MODE
                const filtered = roleFilter === "ALL" ? demoUsers : demoUsers.filter(u => u.role === roleFilter);
                setUsers(filtered);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [roleFilter]);

    const toggleActivation = async (user: User) => {
        setActionLoading(user.id);
        try {
            if (user.is_active) {
                await userService.deactivate(user.id);
            } else {
                await userService.activate(user.id);
            }
            setUsers((prev) =>
                prev.map((u) =>
                    u.id === user.id ? { ...u, is_active: !u.is_active } : u
                )
            );
        } catch {
            // handle error
        } finally {
            setActionLoading(null);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <Users size={24} className="text-indigo-500" />
                    User Management
                </h1>
                <p className="text-sm text-[var(--color-muted-foreground)]">
                    Manage user accounts and roles
                </p>
            </div>

            {/* Role Filters */}
            <div className="flex flex-wrap gap-2">
                {roleFilters.map((r) => (
                    <button
                        key={r}
                        onClick={() => setRoleFilter(r)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${roleFilter === r
                            ? "bg-indigo-600 text-white"
                            : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:bg-[var(--color-border)]"
                            }`}
                    >
                        {r === "ALL" ? "All Roles" : r.replace(/_/g, " ")}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-48">
                    <Loader2 size={28} className="animate-spin text-indigo-500" />
                </div>
            ) : (
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-[var(--color-border)] bg-[var(--color-muted)]">
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Email
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Role
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Status
                                    </th>
                                    <th className="text-left px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Joined
                                    </th>
                                    <th className="text-right px-4 py-3 font-medium text-[var(--color-muted-foreground)]">
                                        Actions
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user) => (
                                    <tr
                                        key={user.id}
                                        className="border-b border-[var(--color-border)] hover:bg-[var(--color-muted)]/50 transition-colors"
                                    >
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs font-semibold shrink-0">
                                                    {user.email.charAt(0).toUpperCase()}
                                                </div>
                                                <span className="font-medium">{user.email}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span
                                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${roleColors[user.role] || ""
                                                    }`}
                                            >
                                                <Shield size={12} />
                                                {user.role.replace(/_/g, " ")}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span
                                                className={`inline-flex items-center gap-1 text-xs font-medium ${user.is_active
                                                    ? "text-emerald-500"
                                                    : "text-red-500"
                                                    }`}
                                            >
                                                {user.is_active ? (
                                                    <CheckCircle2 size={14} />
                                                ) : (
                                                    <XCircle size={14} />
                                                )}
                                                {user.is_active ? "Active" : "Inactive"}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-[var(--color-muted-foreground)]">
                                            {formatDate(user.created_at)}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => toggleActivation(user)}
                                                disabled={actionLoading === user.id}
                                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${user.is_active
                                                    ? "bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-950/50"
                                                    : "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-950/50"
                                                    }`}
                                            >
                                                {actionLoading === user.id ? (
                                                    <Loader2 size={14} className="animate-spin" />
                                                ) : user.is_active ? (
                                                    "Deactivate"
                                                ) : (
                                                    "Activate"
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {users.length === 0 && (
                        <div className="flex items-center justify-center py-12 text-sm text-[var(--color-muted-foreground)]">
                            No users found
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
