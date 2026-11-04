import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ThreadMind AI",
  description:
    "Industrial intelligence for textile manufacturing: quality inspection, machine health, and evidence-grounded root cause investigation.",
};

/**
 * Clerk wraps the whole tree so `auth()` and the token helper are available in server components.
 *
 * The publishable key is public by design (it is the browser's copy of the Frontend API address);
 * the secret key never reaches this bundle. If the publishable key is missing the app fails loudly
 * at build time rather than rendering a dashboard nobody can authenticate against.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!publishableKey) {
    throw new Error(
      "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is not set. Clerk is the only supported identity provider " +
        "for the dashboard; see docs/authentication.md.",
    );
  }

  return (
    <ClerkProvider publishableKey={publishableKey}>
      <html lang="en">
        <body style={{ margin: 0, fontFamily: "ui-sans-serif, system-ui, sans-serif" }}>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
