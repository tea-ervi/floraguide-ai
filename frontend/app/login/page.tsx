"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell from "../components/AuthShell";
import PasswordField from "../components/PasswordField";
import { login } from "../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось войти.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Вход"
      subtitle="Войдите, чтобы видеть свои растения и напоминания о поливе."
      footer={
        <>
          Нет аккаунта? <Link href="/register">Зарегистрироваться</Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="auth-form" noValidate>
        <div className="auth-field">
          <label htmlFor="email" className="auth-label">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            className="auth-input"
          />
        </div>

        <PasswordField
          label="Пароль"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        {error && <p className="auth-error" role="alert">{error}</p>}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? "Входим…" : "Войти"}
        </button>
      </form>
    </AuthShell>
  );
}
