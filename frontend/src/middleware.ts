import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/register", "/"];

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;
    const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "?"));

    // We check for the cookie-reflected token OR just let client handle it
    // Since we use localStorage (client-side only), we do a lightweight check:
    // If path is protected and user has no auth cookie, redirect to login.
    // The actual auth state is enforced by client-side guards in each page.

    if (!isPublic) {
        // The access_token is in localStorage (not cookie), so we can't read it in middleware.
        // Route protection is handled client-side via useAuthStore in each layout.
        // Middleware just passes through here — the per-page guard handles redirects.
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
