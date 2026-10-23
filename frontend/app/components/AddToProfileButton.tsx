"use client";

import { FormEvent, useId, useState } from "react";
import Link from "next/link";
import { addMyPlant, type AddPlantPayload } from "@/app/lib/accounts";
import { useAuth } from "@/app/lib/auth-context";
import { todayInputValue } from "@/app/lib/format";

type Props = {
  plantId: number;
  /** Рекомендуемый интервал полива для этого вида (середина диапазона) */
  suggestedDays?: number;
  /** true, если интервал вычислен по данным о виде, false, если это запасное значение */
  fromSpecies?: boolean;
};

export default function AddToProfileButton({ plantId, suggestedDays = 7, fromSpecies = false }: Props) {
  const { status } = useAuth();
  const uid = useId();

  const [open, setOpen] = useState(false);
  const [customName, setCustomName] = useState("");
  const [plantedAt, setPlantedAt] = useState("");
  const [interval, setIntervalDays] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState(false);

  function openForm() {
    setPlantedAt(todayInputValue()); // дата вычисляется в браузере, чтобы не расходиться с сервером
    setError("");
    setAdded(false);
    setOpen(true);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    const payload: AddPlantPayload = { plant_id: plantId };
    if (customName.trim()) payload.custom_name = customName.trim();
    if (plantedAt) payload.planted_at = plantedAt;
    if (interval.trim()) {
      const days = Number(interval);
      if (!Number.isInteger(days) || days < 1 || days > 365) {
        setError("Интервал полива должен быть целым числом от 1 до 365 дней.");
        return;
      }
      payload.watering_interval_days = days;
    }

    setPending(true);
    try {
      await addMyPlant(payload);
      setAdded(true);
      setOpen(false);
      setCustomName("");
      setIntervalDays("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось добавить растение.");
    } finally {
      setPending(false);
    }
  }

  if (status === "guest") {
    return (
      <div>
        <Link href="/login" className="add-btn">
          Войти, чтобы добавить в мои растения
        </Link>
        <p className="add-note">
          Нет аккаунта? <Link href="/register">Зарегистрируйтесь</Link>
        </p>
      </div>
    );
  }

  if (status === "loading" || status === "error") {
    return (
      <div>
        <button type="button" className="add-btn" disabled>
          Добавить в мои растения
        </button>
        {status === "error" && (
          <p className="add-note">Не удалось проверить вход: сервер недоступен.</p>
        )}
      </div>
    );
  }

  return (
    <div>
      {added && (
        <div className="add-success" role="status">
          Растение добавлено в ваш профиль.{" "}
          <Link href="/profile">Открыть профиль</Link>
        </div>
      )}

      {!open && (
        <button type="button" className="add-btn" onClick={openForm}>
          {added ? "Добавить ещё одно" : "Добавить в мои растения"}
        </button>
      )}

      {open && (
        <form className="add-form" onSubmit={handleSubmit}>
          <h3 className="add-form-title">Добавить в мои растения</h3>

          <div className="add-field">
            <label htmlFor={`${uid}-name`}>Название (необязательно)</label>
            <input
              id={`${uid}-name`}
              type="text"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              maxLength={100}
              placeholder="Например, «Монстера в гостиной»"
            />
          </div>

          <div className="add-row">
            <div className="add-field">
              <label htmlFor={`${uid}-date`}>Дата посадки</label>
              <input
                id={`${uid}-date`}
                type="date"
                value={plantedAt}
                max={todayInputValue()}
                onChange={(e) => setPlantedAt(e.target.value)}
              />
            </div>

            <div className="add-field">
              <label htmlFor={`${uid}-interval`}>Полив раз в … дней</label>
              <input
                id={`${uid}-interval`}
                type="number"
                min={1}
                max={365}
                inputMode="numeric"
                value={interval}
                onChange={(e) => setIntervalDays(e.target.value)}
                placeholder={String(suggestedDays)}
              />
            </div>
          </div>

          <p className="add-note">
            {fromSpecies
              ? `Если не указать, будет ${suggestedDays} дн.: середина рекомендуемого диапазона для этого растения.`
              : "Для этого растения нет данных о поливе, по умолчанию будет 7 дней."}
          </p>

          {error && (
            <p className="add-error" role="alert">
              {error}
            </p>
          )}

          <div className="add-form-actions">
            <button type="submit" className="add-btn" disabled={pending}>
              {pending ? "Добавляем…" : "Добавить"}
            </button>
            <button type="button" className="add-btn-ghost" onClick={() => setOpen(false)} disabled={pending}>
              Отмена
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
