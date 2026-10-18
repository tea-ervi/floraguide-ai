"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell from "../components/AuthShell";
import PasswordField from "../components/PasswordField";
import { login, register } from "../lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const mismatch = repeat.length > 0 && password !== repeat;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Пароль должен быть не короче 8 символов.");
      return;
    }
    if (password.length > 72) {
      setError("Пароль должен быть не длиннее 72 символов.");
      return;
    }
    if (password !== repeat) {
      setError("Пароли не совпадают.");
      return;
    }

    setLoading(true);
    try {
      const normalized = email.trim().toLowerCase();
      await register(normalized, password);
      await login(normalized, password); // сразу входим после регистрации
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось зарегистрироваться.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Регистрация"
      subtitle="Создайте аккаунт, чтобы сохранять растения и следить за поливом."
      footer={
        <>
          Уже есть аккаунт? <Link href="/login">Войти</Link>
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
          autoComplete="new-password"
          hint="От 8 до 72 символов."
        />

        <PasswordField
          label="Повторите пароль"
          value={repeat}
          onChange={setRepeat}
          autoComplete="new-password"
          hint={mismatch ? "Пароли не совпадают." : undefined}
        />

        {error && <p className="auth-error" role="alert">{error}</p>}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? "Создаём аккаунт…" : "Зарегистрироваться"}
        </button>
      </form>
    </AuthShell>
  );
}
