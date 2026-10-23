export const FALLBACK_INTERVAL_DAYS = 7;

/**
 * Рекомендуемый интервал полива: середина диапазона из данных о виде.
 * (5, 7) → 6;  (7, 10) → 8;  задана одна граница → она сама;  данных нет → 7.
 * Правило совпадает с suggested_interval() в backend/app/crud/user_plant.py.
 */
export function suggestedIntervalDays(
  min: number | null,
  max: number | null,
): { days: number; fromSpecies: boolean } {
  const values = [min, max].filter((v): v is number => typeof v === "number" && v > 0);
  if (values.length === 0) return { days: FALLBACK_INTERVAL_DAYS, fromSpecies: false };
  const sum = values.reduce((a, b) => a + b, 0);
  return { days: Math.max(1, Math.min(365, Math.floor(sum / values.length))), fromSpecies: true };
}
