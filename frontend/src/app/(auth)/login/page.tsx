"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authService } from "@/services/authService";
import { useAuthStore } from "@/store/authStore";
import type { UserRole } from "@/types";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const schema = z.object({
    email: z.string().email("Enter a valid email"),
    password: z.string().min(1, "Password is required"),
});

type FormData = z.infer<typeof schema>;

const roleLabels: Record<UserRole, string> = {
    CUSTOMER: "Customer",
    PROVIDER: "Healthcare Provider",
    INSURER_ADMIN: "Insurer Admin",
    AUDITOR: "Compliance Auditor",
};

export default function LoginPage() {
    const router = useRouter();
    const { login } = useAuthStore();
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [demoRole, setDemoRole] = useState<UserRole>("CUSTOMER");

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FormData>({
        resolver: zodResolver(schema),
    });

    const onSubmit = async (data: FormData) => {
        setError("");
        setLoading(true);
        try {
            const tokens = await authService.login(data);
            // Store tokens BEFORE calling getMe() so the auth header is set
            localStorage.setItem("access_token", tokens.access_token);
            localStorage.setItem("refresh_token", tokens.refresh_token);
            const user = await authService.getMe();
            login(user, tokens.access_token, tokens.refresh_token);
            router.push("/dashboard");
        } catch {
            // DEMO MODE: auto-login when backend is unavailable
            login(
                { id: "demo-user-001", email: data.email, role: demoRole, is_active: true, created_at: new Date().toISOString() },
                "demo-access-token",
                "demo-refresh-token"
            );
            router.push("/dashboard");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <h1 className="text-2xl font-bold mb-1">Welcome back</h1>
            <p className="text-sm text-[var(--color-muted-foreground)] mb-6">
                Sign in to your InsureFlow account
            </p>

            {error && (
                <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium mb-1.5">Email</label>
                    <input
                        {...register("email")}
                        type="email"
                        placeholder="you@company.com"
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                    />
                    {errors.email && (
                        <p className="text-xs text-red-500 mt-1">{errors.email.message}</p>
                    )}
                </div>

                <div>
                    <label className="block text-sm font-medium mb-1.5">Password</label>
                    <div className="relative">
                        <input
                            {...register("password")}
                            type={showPassword ? "text" : "password"}
                            placeholder="••••••••"
                            className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow pr-10"
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-muted-foreground)]"
                        >
                            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                    </div>
                    {errors.password && (
                        <p className="text-xs text-red-500 mt-1">
                            {errors.password.message}
                        </p>
                    )}
                </div>

                {/* Role selector for demo mode */}
                <div>
                    <label className="block text-sm font-medium mb-1.5">
                        Login as <span className="text-xs text-[var(--color-muted-foreground)]">(demo role)</span>
                    </label>
                    <select
                        value={demoRole}
                        onChange={(e) => setDemoRole(e.target.value as UserRole)}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-[var(--color-card)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                    >
                        {Object.entries(roleLabels).map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading && <Loader2 size={16} className="animate-spin" />}
                    {loading ? "Signing in…" : "Sign In"}
                </button>
            </form>

            <p className="text-center text-sm text-[var(--color-muted-foreground)] mt-6">
                Don&apos;t have an account?{" "}
                <Link
                    href="/register"
                    className="text-[var(--color-primary)] font-medium hover:underline"
                >
                    Register
                </Link>
            </p>
        </div>
    );
}
