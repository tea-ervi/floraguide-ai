"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const QUICK_SEARCHES = ["Монстера", "Суккуленты", "Желтеют листья", "Мало света"];

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSearch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="home-page">
      <header className="home-header">
        <Link href="/" className="home-logo">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <path
              d="M6 26C6 13 14 5 27 5c0 13-8 21-21 21Z"
              fill="currentColor"
            />
            <path
              d="M6 26 20 12"
              stroke="#EEF4E8"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
          </svg>
          FloraGuide
        </Link>

        <nav className="home-auth" aria-label="Аккаунт">
          <Link href="/login" className="home-btn-ghost">
            Войти
          </Link>
          <Link href="/register" className="home-btn-solid">
            Регистрация
          </Link>
        </nav>
      </header>

      <main className="home-hero">
        <div className="home-hero-text">
          <h1 className="home-title">
            Найдите растение и узнайте, как за ним ухаживать
          </h1>
          <p className="home-lead">
            Введите название растения
          </p>

          <form className="home-search" onSubmit={handleSearch} role="search">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Название растения или симптом"
              aria-label="Поиск растений"
              className="home-input"
            />
            <button type="submit" className="home-search-btn">
              Найти
            </button>
          </form>

          <ul className="home-chips">
            {QUICK_SEARCHES.map((item) => (
              <li key={item}>
                <Link
                  href={`/search?q=${encodeURIComponent(item)}`}
                  className="home-chip"
                >
                  {item}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <svg
          className="home-art"
          viewBox="0 0 400 480"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M200 460C60 380 20 220 120 110 160 66 200 40 200 20c0 20 40 46 80 90 100 110 60 270-80 350Z"
            fill="#7DAA5B"
            opacity="0.35"
          />
          <path
            d="M200 460V120M200 330 130 260M200 270 270 200M200 210 140 160"
            stroke="#2F5D3A"
            strokeWidth="6"
            strokeLinecap="round"
            fill="none"
            opacity="0.5"
          />
        </svg>
      </main>
    </div>
  );
}
