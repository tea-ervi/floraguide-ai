// Запросы к API курсов. Работают и на сервере (страницы курсов), и в браузере (тест).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type CourseSummary = {
  slug: string;
  title: string;
  description: string;
  topic: string;
  topic_label: string;
  level: string;
  duration_minutes: number;
  questions_count: number;
};

export type CourseDetail = CourseSummary & {
  notes: string;
  sources: { title: string; url: string }[];
};

export type TestQuestion = {
  id: string;
  topic: string;
  situation: string;
  question: string;
  options: { id: string; text: string }[];
};

export type TestData = { course: string; title: string; questions: TestQuestion[] };
export type CheckResult = { correct: boolean; feedback: string };

export class CourseError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new CourseError("Не удалось связаться с сервером. Проверьте, что бэкенд запущен.");
  }
  if (res.status === 404) throw new CourseError("Не найдено", 404);
  if (!res.ok) throw new CourseError("Что-то пошло не так. Попробуйте ещё раз.", res.status);
  return res.json();
}

export const getCourses = () => request<CourseSummary[]>("/courses");

export const getCourse = (slug: string) => request<CourseDetail>(`/courses/${encodeURIComponent(slug)}`);

export const getTest = (slug: string) => request<TestData>(`/courses/${encodeURIComponent(slug)}/test`);

export const checkAnswer = (slug: string, questionId: string, optionId: string) =>
  request<CheckResult>(`/courses/${encodeURIComponent(slug)}/test/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, option_id: optionId }),
  });
