import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Route protection at the edge.
 *
 * Only the health probe and the sign-in/up flows are public. Everything else requires a session
 * before a page renders, so an unauthenticated visitor never sees the shell of a dashboard and then
 * a scattering of failed requests.
 *
 * This is not the authorization boundary - the API verifies every token it receives and PostgreSQL
 * enforces tenancy per row. A client that skips this middleware gains nothing.
 */
const isPublic = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublic(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
