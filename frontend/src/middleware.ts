/**
 * RetailFlow AI — Next.js Middleware
 *
 * Protects dashboard routes by checking for the rf_token cookie.
 * The actual JWT validation happens server-side at the FastAPI layer;
 * here we just gate navigation client-side for UX.
 */
import { type NextRequest, NextResponse } from "next/server";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/analytics",
  "/stores",
  "/notifications",
  "/ml",
  "/settings",
];

const AUTH_ROUTES = ["/login", "/register"];

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const hasRefreshCookie = request.cookies.has("rf_token");

  const isProtected = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix),
  );
  const isAuthRoute = AUTH_ROUTES.some((route) =>
    pathname.startsWith(route),
  );

  // Redirect unauthenticated users away from protected pages
  if (isProtected && !hasRefreshCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect authenticated users away from auth pages
  if (isAuthRoute && hasRefreshCookie) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all routes except:
     * - _next/static (static files)
     * - _next/image (Next.js image optimization)
     * - favicon.ico
     * - /api/* (Next.js API routes, not our backend)
     * - /queue/* (public customer app — no auth)
     */
    "/((?!_next/static|_next/image|favicon.ico|api/|queue/).*)",
  ],
};
