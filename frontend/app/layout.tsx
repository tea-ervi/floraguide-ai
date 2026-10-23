import type { Metadata } from "next";
import "./globals.css";
import "./footer-and-warning.css";
import { AuthProvider } from "./lib/auth-context";
import SiteFooter from "./components/SiteFooter";

export const metadata: Metadata = {
  title: "FloraGuide",
  description: "Уход за комнатными растениями",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>
        <AuthProvider>
          {children}
          <SiteFooter />
        </AuthProvider>
      </body>
    </html>
  );
}