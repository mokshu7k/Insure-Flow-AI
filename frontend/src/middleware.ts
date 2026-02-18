import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const publicPaths = ["/", "/login", "/register"];

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Allow public paths and static assets
    if (
        publicPaths.includes(pathname) ||
        pathname.startsWith("/_next") ||
        pathname.startsWith("/api") ||
        pathname.includes(".")
    ) {
        return NextResponse.next();
    }

    // Check for auth token in cookies (server-side) — we also store in localStorage client-side
    const token = request.cookies.get("access_token")?.value;

    // If no cookie token, redirect to login
    // Note: Our primary auth is via localStorage + Zustand (client-side),
    // so this middleware is a fallback for direct URL navigation.
    // The client-side AuthGuard component handles the main protection.
    if (!token) {
        // We don't strictly redirect here because auth is managed client-side
        // Instead, the page components themselves check auth state
        return NextResponse.next();
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        "/((?!_next/static|_next/image|favicon.ico|.*\\..*$).*)",
    ],
};
