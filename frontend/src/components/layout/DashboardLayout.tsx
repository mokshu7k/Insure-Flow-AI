"use client";

import Sidebar from "./Sidebar";
import Header from "./Header";
import AuthGuard from "@/components/auth/AuthGuard";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <AuthGuard>
            <div className="flex min-h-screen">
                <Sidebar />
                <div className="flex-1 flex flex-col min-w-0">
                    <Header />
                    <main className="flex-1 p-6 overflow-auto">{children}</main>
                </div>
            </div>
        </AuthGuard>
    );
}
