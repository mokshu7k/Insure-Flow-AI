export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-600/10 via-purple-600/5 to-[var(--background)] relative overflow-hidden">
            {/* Decorative blobs */}
            <div className="absolute top-10 left-10 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl" />
            <div className="absolute bottom-10 right-10 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

            <div className="relative z-10 w-full max-w-md mx-auto px-4">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white">
                            IF
                        </div>
                        <span className="font-bold text-xl">InsureFlow AI</span>
                    </div>
                </div>

                {/* Card */}
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl shadow-xl p-8">
                    {children}
                </div>

                <p className="text-center text-xs text-[var(--color-muted-foreground)] mt-6">
                    © 2026 InsureFlow AI. All rights reserved.
                </p>
            </div>
        </div>
    );
}
