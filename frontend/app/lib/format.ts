/** Дата без времени («2026-10-16») как локальная дата, без сдвига часового пояса. */
export function parseDateOnly(value: string | null): Date | null {
  if (!value) return null;
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

/** Бэкенд хранит время в UTC без указания пояса: дописываем «Z», если его нет. */
export function parseUtcDateTime(value: string | null): Date | null {
  if (!value) return null;
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(date: Date | null, withYear = true): string {
  if (!date) return "—";
  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    ...(withYear ? { year: "numeric" } : {}),
  });
}

export function formatMonthYear(date: Date | null): string {
  if (!date) return "—";
  return date.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
}

/** Сколько дней от сегодняшнего (локального) дня до даты. Отрицательное: дата прошла. */
export function daysFromToday(date: Date): number {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((date.getTime() - today.getTime()) / 86_400_000);
}

/** Сегодняшняя дата в формате для <input type="date">. */
export function todayInputValue(): string {
  const now = new Date();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${mm}-${dd}`;
}