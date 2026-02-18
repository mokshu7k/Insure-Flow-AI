"use client";

import { useAuthStore } from "@/store/authStore";
import { Bell, Search } from "lucide-react";

export default function Header() {
    const { user } = useAuthStore();

    return (
        <header className="h-16 border-b border-[var(--color-border)] bg-[var(--color-card)] flex items-center justify-between px-6 sticky top-0 z-30">
            {/* Search */}
            <div className="flex items-center gap-2 bg-[var(--color-muted)] rounded-lg px-3 py-2 w-80">
                <Search size={16} className="text-[var(--color-muted-foreground)]" />
                <input
                    type="text"
                    placeholder="Search claims, users..."
                    className="bg-transparent outline-none text-sm flex-1 placeholder:text-[var(--color-muted-foreground)]"
                />
            </div>

            {/* Right side */}
            <div className="flex items-center gap-4">
                {/* Notifications */}
                <button className="relative p-2 rounded-lg hover:bg-[var(--color-muted)] transition-colors">
                    <Bell size={20} className="text-[var(--color-muted-foreground)]" />
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
                </button>

                {/* User */}
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-white text-xs font-semibold">
                        {user?.email?.charAt(0).toUpperCase() || "U"}
                    </div>
                    <div className="hidden sm:block">
                        <p className="text-sm font-medium leading-none">
                            {user?.email || "User"}
                        </p>
                        <p className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
                            {user?.role?.replace("_", " ") || ""}
                        </p>
                    </div>
                </div>
            </div>
        </header>
    );
}
