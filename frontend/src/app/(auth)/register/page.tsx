"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authService } from "@/services/authService";
import { Eye, EyeOff, Loader2 } from "lucide-react";

const schema = z
    .object({
        email: z.string().email("Enter a valid email"),
        password: z.string().min(8, "Minimum 8 characters"),
        confirmPassword: z.string(),
        role: z.enum(["CUSTOMER", "PROVIDER", "INSURER_ADMIN", "AUDITOR"], {
            message: "Select a role",
        }),
    })
    .refine((data) => data.password === data.confirmPassword, {
        message: "Passwords don't match",
        path: ["confirmPassword"],
    });

type FormData = z.infer<typeof schema>;

const roleLabels = {
    CUSTOMER: "Customer",
    PROVIDER: "Healthcare Provider",
    INSURER_ADMIN: "Insurer Admin",
    AUDITOR: "Compliance Auditor",
};

export default function RegisterPage() {
    const router = useRouter();
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

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
            await authService.register({
                email: data.email,
                password: data.password,
                role: data.role,
            });
            router.push("/login");
        } catch {
            // DEMO MODE: skip to login when backend is unavailable
            router.push("/login");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <h1 className="text-2xl font-bold mb-1">Create account</h1>
            <p className="text-sm text-[var(--color-muted-foreground)] mb-6">
                Get started with InsureFlow AI
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
                            placeholder="Min 8 characters"
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

                <div>
                    <label className="block text-sm font-medium mb-1.5">
                        Confirm Password
                    </label>
                    <input
                        {...register("confirmPassword")}
                        type="password"
                        placeholder="••••••••"
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-transparent text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                    />
                    {errors.confirmPassword && (
                        <p className="text-xs text-red-500 mt-1">
                            {errors.confirmPassword.message}
                        </p>
                    )}
                </div>

                <div>
                    <label className="block text-sm font-medium mb-1.5">Role</label>
                    <select
                        {...register("role")}
                        className="w-full px-3 py-2.5 rounded-lg border border-[var(--color-input)] bg-[var(--color-card)] text-sm outline-none focus:ring-2 focus:ring-[var(--color-ring)] focus:border-transparent transition-shadow"
                    >
                        <option value="">Select a role…</option>
                        {Object.entries(roleLabels).map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                    {errors.role && (
                        <p className="text-xs text-red-500 mt-1">{errors.role.message}</p>
                    )}
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {loading && <Loader2 size={16} className="animate-spin" />}
                    {loading ? "Creating account…" : "Create Account"}
                </button>
            </form>

            <p className="text-center text-sm text-[var(--color-muted-foreground)] mt-6">
                Already have an account?{" "}
                <Link
                    href="/login"
                    className="text-[var(--color-primary)] font-medium hover:underline"
                >
                    Sign In
                </Link>
            </p>
        </div>
    );
}
