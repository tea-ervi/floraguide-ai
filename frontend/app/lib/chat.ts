// Запросы к чату растения. Вызываются только в браузере, нужен токен входа.
import { AccountError, clearToken, getToken, type UserPlant } from "./accounts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type AnswerValue = "yes" | "no" | "unknown";

export type ChatOption = { label: string; value: AnswerValue };
export type ChatQuestion = { symptom: string; text: string; options: ChatOption[] };
export type Suggestion = { label: string; text: string };

export type Diagnosis = {
  cause: string;
  name: string;
  confidence: number;          // 1-99
  confident: boolean;          // false: данных пока недостаточно
  urgency: "low" | "medium" | "high";
  summary: string;
  steps: string[];
  why: string[];
  against: string[];
  alternatives: { cause: string; name: string; confidence: number }[];
  sources: { title: string; url: string }[];
};

export type ReplyMeta = {
  kind: "question" | "diagnosis" | "uncertain" | "need_info" | "info";
  text: string;
  question?: ChatQuestion | null;
  diagnosis?: Diagnosis | null;
  suggestions?: Suggestion[] | null;
};

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  meta: ReplyMeta | null;
  created_at: string;
};

export type SendBody = { text: string } | { answer: { symptom: string; value: AnswerValue } };

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      return String(data.detail[0].msg).replace(/^Value error, /, "");
    }
  } catch {
    /* тело ответа не JSON */
  }
  return "Что-то пошло не так. Попробуйте ещё раз.";
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
    clearToken();
    throw new AccountError("Сессия истекла. Войдите снова.", 401);
  }
  if (!res.ok) throw new AccountError(await readError(res), res.status);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const getMyPlant = (id: number) => request<UserPlant>(`/me/plants/${id}`);

export const getChat = (id: number) =>
  request<{ messages: ChatMessage[] }>(`/me/plants/${id}/chat`);

export const sendChat = (id: number, body: SendBody) =>
  request<{ user_message: ChatMessage; assistant_message: ChatMessage }>(`/me/plants/${id}/chat`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const resetChat = (id: number) => request<void>(`/me/plants/${id}/chat`, { method: "DELETE" });
