"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth-context";

export default function AuthNav({ className = "home-auth" }: { className?: string }) {
  const { status, logout } = useAuth();

  if (status === "authed") {
    return (
      <nav className={className} aria-label="Аккаунт">
        <Link href="/profile" className="home-btn-solid">
          Профиль
        </Link>
        <button type="button" onClick={logout} className="home-btn-ghost">
          Выйти
        </button>
      </nav>
    );
  }

  if (status === "loading") {
    // Пустой блок того же размера, чтобы шапка не прыгала
    return <nav className={className} aria-label="Аккаунт" aria-busy="true" style={{ minWidth: 230, minHeight: 44 }} />;
  }

  return (
    <nav className={className} aria-label="Аккаунт">
      <Link href="/login" className="home-btn-ghost">
        Войти
      </Link>
      <Link href="/register" className="home-btn-solid">
        Регистрация
      </Link>
    </nav>
  );
}
