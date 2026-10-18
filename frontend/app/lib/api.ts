const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const TOKEN_KEY = "access_token";

export class ApiError extends Error {}

/** Достаёт читаемое сообщение из ответа FastAPI (400/401 — строка, 422 — массив). */
async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
      if (field === "email") return "Введите корректный email.";
      if (field === "password") return "Пароль должен быть от 8 до 72 символов.";
      return first.msg ?? fallback;
    }
  } catch {
    /* тело ответа не JSON */
  }
  return fallback;
}

async function request(path: string, init: RequestInit, fallback: string) {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("Не удалось связаться с сервером. Проверьте, что бэкенд запущен.");
  }
  if (!res.ok) throw new ApiError(await readError(res, fallback));
  return res.json();
}

export async function login(email: string, password: string): Promise<void> {
  // /auth/login ждёт форму OAuth2: поле username — это email
  const body = new URLSearchParams({ username: email, password });
  const data = await request(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    },
    "Не удалось войти. Попробуйте ещё раз."
  );
  localStorage.setItem(TOKEN_KEY, data.access_token);
}

export async function register(email: string, password: string): Promise<void> {
  await request(
    "/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    "Не удалось зарегистрироваться. Попробуйте ещё раз."
  );
}
