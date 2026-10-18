"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import SiteHeader from "../components/SiteHeader";
import {
  AccountError,
  deleteMyPlant,
  getMyPlants,
  waterMyPlant,
  type UserPlant,
} from "../lib/accounts";
import { useAuth } from "../lib/auth-context";
import { plural } from "../lib/catalog";
import {
  daysFromToday,
  formatDate,
  formatMonthYear,
  parseDateOnly,
  parseUtcDateTime,
} from "../lib/format";

type Tone = "overdue" | "today" | "soon" | "later" | "none";

function waterStatus(plant: UserPlant): { label: string; tone: Tone } {
  const next = parseDateOnly(plant.next_watering_date);
  if (!next) return { label: "Дата не определена", tone: "none" };

  const d = daysFromToday(next);
  if (d < 0) {
    return { label: `Просрочено на ${-d} ${plural(-d, "день", "дня", "дней")}`, tone: "overdue" };
  }
  if (d === 0) return { label: "Полить сегодня", tone: "today" };
  if (d === 1) return { label: "Полить завтра", tone: "soon" };
  return { label: `Через ${d} ${plural(d, "день", "дня", "дней")}`, tone: d <= 2 ? "soon" : "later" };
}

function sortByWatering(list: UserPlant[]): UserPlant[] {
  return [...list].sort((a, b) => {
    if (!a.next_watering_date) return b.next_watering_date ? 1 : 0;
    if (!b.next_watering_date) return -1;
    return a.next_watering_date.localeCompare(b.next_watering_date);
  });
}

export default function ProfilePage() {
  const router = useRouter();
  const { status, user, errorMessage } = useAuth();

  const [plants, setPlants] = useState<UserPlant[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  // Не вошёл: отправляем на страницу входа
  useEffect(() => {
    if (status === "guest") router.replace("/login");
  }, [status, router]);

  function handleError(err: unknown) {
    if (err instanceof AccountError && err.status === 401) {
      router.replace("/login");
      return;
    }
    setError(err instanceof Error ? err.message : "Что-то пошло не так. Попробуйте ещё раз.");
  }

  useEffect(() => {
    if (status !== "authed") return;
    let cancelled = false;
    getMyPlants()
      .then((data) => {
        if (!cancelled) setPlants(sortByWatering(data));
      })
      .catch((err) => {
        if (!cancelled) handleError(err);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  async function handleWater(id: number) {
    setBusyId(id);
    setError("");
    try {
      const updated = await waterMyPlant(id);
      setPlants((prev) => (prev ? sortByWatering(prev.map((p) => (p.id === id ? updated : p))) : prev));
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(plant: UserPlant) {
    if (!window.confirm(`Удалить «${plant.display_name}» из ваших растений?`)) return;
    setBusyId(plant.id);
    setError("");
    try {
      await deleteMyPlant(plant.id);
      setPlants((prev) => (prev ? prev.filter((p) => p.id !== plant.id) : prev));
    } catch (err) {
      handleError(err);
    } finally {
      setBusyId(null);
    }
  }

  const stats = useMemo(() => {
    const list = plants ?? [];
    let needWater = 0;
    let nearest: Date | null = null;
    for (const p of list) {
      const next = parseDateOnly(p.next_watering_date);
      if (!next) continue;
      if (daysFromToday(next) <= 0) needWater += 1;
      if (!nearest || next < nearest) nearest = next;
    }
    return { total: list.length, needWater, nearest };
  }, [plants]);

  return (
    <div className="pf-page">
      <SiteHeader />

      <main className="pf-main">
        {(status === "loading" || status === "guest") && <p className="pf-muted">Загрузка…</p>}

        {status === "error" && (
          <div className="pf-notice pf-notice-error" role="alert">
            {errorMessage}
          </div>
        )}

        {status === "authed" && user && (
          <>
            <section className="pf-card" aria-labelledby="pf-heading">
              <div className="pf-avatar" aria-hidden="true">
                {user.email.charAt(0).toUpperCase()}
              </div>

              <div className="pf-card-info">
                <h1 id="pf-heading" className="pf-title">
                  Мой профиль
                </h1>
                <p className="pf-email">{user.email}</p>
                <p className="pf-since">На сайте с {formatMonthYear(parseUtcDateTime(user.created_at))}</p>
              </div>

              <dl className="pf-stats">
                <div className="pf-stat">
                  <dt>Растений</dt>
                  <dd>{stats.total}</dd>
                </div>
                <div className="pf-stat">
                  <dt>Нужно полить</dt>
                  <dd>{stats.needWater}</dd>
                </div>
                <div className="pf-stat">
                  <dt>Ближайший полив</dt>
                  <dd>{formatDate(stats.nearest, false)}</dd>
                </div>
              </dl>
            </section>

            <div className="pf-section-head">
              <h2 className="pf-section-title">Мои растения</h2>
              <Link href="/search" className="pf-link-btn">
                + Найти растение
              </Link>
            </div>

            {error && (
              <div className="pf-notice pf-notice-error" role="alert">
                {error}
              </div>
            )}

            {plants === null && !error && <p className="pf-muted">Загружаем ваши растения…</p>}

            {plants !== null && plants.length === 0 && (
              <div className="pf-notice">
                <p>Пока здесь пусто. Найдите растение в каталоге и добавьте его в свой профиль.</p>
                <Link href="/search" className="pf-link">
                  Открыть каталог
                </Link>
              </div>
            )}

            {plants !== null && plants.length > 0 && (
              <ul className="pf-grid">
                {plants.map((plant) => {
                  const ws = waterStatus(plant);
                  const busy = busyId === plant.id;
                  return (
                    <li key={plant.id} className="pf-plant">
                      <div className="pf-plant-top">
                        <span className="pf-tag">{plant.species.category.name}</span>
                        <span className={`pf-badge pf-badge-${ws.tone}`}>{ws.label}</span>
                      </div>

                      <h3 className="pf-plant-name">
                        <Link href={`/plants/${plant.species.id}`}>{plant.display_name}</Link>
                      </h3>
                      {plant.custom_name && <p className="pf-plant-species">{plant.species.name}</p>}

                      <dl className="pf-meta">
                        <div>
                          <dt>Посажено</dt>
                          <dd>{formatDate(parseDateOnly(plant.planted_at))}</dd>
                        </div>
                        <div>
                          <dt>Последний полив</dt>
                          <dd>
                            {plant.last_watered_at
                              ? formatDate(parseUtcDateTime(plant.last_watered_at))
                              : "ещё не поливали"}
                          </dd>
                        </div>
                        <div>
                          <dt>Следующий полив</dt>
                          <dd>{formatDate(parseDateOnly(plant.next_watering_date))}</dd>
                        </div>
                        <div>
                          <dt>Интервал</dt>
                          <dd>
                            {plant.watering_interval_days
                              ? `каждые ${plant.watering_interval_days} дн.`
                              : "—"}
                          </dd>
                        </div>
                      </dl>

                      <div className="pf-actions">
                        <button
                          type="button"
                          className="pf-btn"
                          onClick={() => handleWater(plant.id)}
                          disabled={busy}
                        >
                          {busy ? "Подождите…" : "Полито"}
                        </button>
                        <button
                          type="button"
                          className="pf-btn-ghost"
                          onClick={() => handleDelete(plant)}
                          disabled={busy}
                        >
                          Удалить
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </main>
    </div>
  );
}