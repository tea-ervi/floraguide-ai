import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./lib/auth-context";

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
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}