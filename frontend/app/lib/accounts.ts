// Запросы, которым нужен токен: профиль и «Мои растения». Вызываются только в браузере.
import { TOKEN_KEY } from "./api";
import type { PlantListItem } from "./catalog";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type User = {
  id: number;
  email: string;
  created_at: string;
};

export type UserPlant = {
  id: number;
  custom_name: string | null;
  planted_at: string | null;
  last_watered_at: string | null;
  watering_interval_days: number | null;
  species: PlantListItem;
  display_name: string;
  next_watering_date: string | null;
  days_until_watering: number | null;
};

export type AddPlantPayload = {
  plant_id: number;
  custom_name?: string;
  planted_at?: string;
  watering_interval_days?: number;
};

export class AccountError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* хранилище недоступно */
  }
}

async function readError(res: Response): Promise<string> {
  const fallback = "Что-то пошло не так. Попробуйте ещё раз.";
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      return String(data.detail[0].msg).replace(/^Value error, /, "");
    }
  } catch {
    /* тело ответа не JSON */
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  if (!token) throw new AccountError("Войдите в аккаунт.", 401);

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new AccountError("Не удалось связаться с сервером. Проверьте, что бэкенд запущен.");
  }

  if (res.status === 401) {
    clearToken(); // токен просрочен или недействителен
    throw new AccountError("Сессия истекла. Войдите снова.", 401);
  }
  if (!res.ok) throw new AccountError(await readError(res), res.status);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const getMe = () => request<User>("/auth/me");

export const getMyPlants = () => request<UserPlant[]>("/me/plants");

export const addMyPlant = (payload: AddPlantPayload) =>
  request<UserPlant>("/me/plants", { method: "POST", body: JSON.stringify(payload) });

export const waterMyPlant = (id: number) =>
  request<UserPlant>(`/me/plants/${id}/water`, { method: "POST" });

export const deleteMyPlant = (id: number) =>
  request<void>(`/me/plants/${id}`, { method: "DELETE" });