import Link from "next/link";
import AuthNav from "../components/AuthNav";

export default function SiteHeader() {
  return (
    <header className="cat-header">
      <Link href="/" className="home-logo">
        <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
          <path d="M6 26C6 13 14 5 27 5c0 13-8 21-21 21Z" fill="currentColor" />
          <path d="M6 26 20 12" stroke="#EEF4E8" strokeWidth="2" strokeLinecap="round" fill="none" />
        </svg>
        FloraGuide
      </Link>

      {/* Обычная GET-форма: работает без JavaScript и ведёт на /search?q=... */}
      <form action="/search" role="search" className="cat-header-search">
        <input
          type="search"
          name="q"
          maxLength={100}
          placeholder="Найти растение"
          aria-label="Поиск растений"
          className="cat-header-input"
        />
      </form>

      <AuthNav className="cat-auth" />
    </header>
  );
}
