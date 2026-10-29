"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import DiagnosisCard from "../../components/DiagnosisCard";
import SiteHeader from "../../components/SiteHeader";
import { AccountError, type UserPlant } from "../../lib/accounts";
import { useAuth } from "../../lib/auth-context";
import {
  getChat, getMyPlant, resetChat, sendChat,
  type AnswerValue, type ChatMessage, type SendBody, type Suggestion,
} from "../../lib/chat";
import { parseUtcDateTime } from "../../lib/format";

const STARTERS: Suggestion[] = [
  { label: "Желтеют листья", text: "желтеют листья" },
  { label: "Растение поникло", text: "поникло" },
  { label: "Сохнут кончики", text: "сохнут кончики" },
  { label: "Пятна на листьях", text: "коричневые пятна" },
  { label: "Опадают листья", text: "опадают листья" },
  { label: "Паутинка", text: "паутина" },
  { label: "Мошки", text: "мошки" },
  { label: "Когда поливать?", text: "когда поливать?" },
];

function time(message: ChatMessage): string {
  const date = parseUtcDateTime(message.created_at);
  return date ? date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";
}

export default function ChatPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const plantId = Number(params?.id);
  const { status, errorMessage } = useAuth();

  const [plant, setPlant] = useState<UserPlant | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof AccountError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Что-то пошло не так. Попробуйте ещё раз.");
    },
    [router],
  );

  // Не вошёл: на страницу входа
  useEffect(() => {
    if (status === "guest") router.replace("/login");
  }, [status, router]);

  // Растение и история чата
  useEffect(() => {
    if (status !== "authed") return;
    if (!Number.isInteger(plantId) || plantId < 1) {
      setNotFound(true);
      return;
    }
    let cancelled = false;
    Promise.all([getMyPlant(plantId), getChat(plantId)])
      .then(([p, chat]) => {
        if (cancelled) return;
        setPlant(p);
        setMessages(chat.messages);
        setLoaded(true);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof AccountError && err.status === 404) setNotFound(true);
        else handleError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [status, plantId, handleError]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  /** Отправляет сообщение. Возвращает true, если ответ получен. */
  async function submit(body: SendBody, shownText: string): Promise<boolean> {
    if (sending) return false;
    setError("");
    setSending(true);
    const temp: ChatMessage = {
      id: -Date.now(), role: "user", text: shownText, meta: null, created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, temp]);
    try {
      const res = await sendChat(plantId, body);
      setMessages((prev) => [...prev.filter((m) => m.id !== temp.id), res.user_message, res.assistant_message]);
      return true;
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== temp.id));
      handleError(err);
      return false;
    } finally {
      setSending(false);
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    if (await submit({ text }, text)) setInput("");
  }

  function answer(symptom: string, value: AnswerValue, label: string) {
    void submit({ answer: { symptom, value } }, label);
  }

  async function handleReset() {
    if (!window.confirm("Начать разговор заново? История этого чата будет удалена.")) return;
    try {
      await resetChat(plantId);
      setMessages([]);
      setError("");
    } catch (err) {
      handleError(err);
    }
  }

  const last = messages[messages.length - 1];
  const lastMeta = last?.role === "assistant" ? last.meta : null;
  const name = plant?.display_name ?? "растение";

  return (
    <div className="pf-page">
      <SiteHeader />

      <main className="chat-main">
        <Link href="/profile" className="chat-back">
          ← Мои растения
        </Link>

        {(status === "loading" || status === "guest") && <p className="pf-muted">Загрузка…</p>}

        {status === "error" && (
          <div className="pf-notice pf-notice-error" role="alert">
            {errorMessage}
          </div>
        )}

        {notFound && (
          <div className="pf-notice">
            <p>Растение не найдено в вашем профиле.</p>
            <Link href="/profile" className="pf-link">
              Вернуться к моим растениям
            </Link>
          </div>
        )}

        {status === "authed" && !notFound && (
          <>
            <div className="chat-title-row">
              <h1 className="chat-title">Чат: {name}</h1>
              {messages.length > 0 && (
                <button type="button" className="pf-btn-ghost" onClick={handleReset} disabled={sending}>
                  Начать заново
                </button>
              )}
            </div>

            {!loaded && <p className="pf-muted">Загружаем чат…</p>}

            {loaded && (
              <div className="chat-log" role="log" aria-live="polite" aria-label="История чата">
                {messages.length === 0 && (
                  <div className="chat-row chat-row-bot">
                    <div className="chat-bubble chat-bubble-bot">
                      <p className="chat-text">
                        Здравствуйте! Опишите своими словами, что не так с растением «{name}», например:
                        «листья желтеют» или «земля мокрая». Я задам уточняющие вопросы и объясню, почему сделала такой вывод.
                      </p>
                      <div className="chat-chips">
                        {STARTERS.map((s) => (
                          <button
                            key={s.text}
                            type="button"
                            className="chat-chip"
                            disabled={sending}
                            onClick={() => void submit({ text: s.text }, s.label)}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {messages.map((m) => {
                  const isLast = m === last;
                  if (m.role === "user") {
                    return (
                      <div key={m.id} className="chat-row chat-row-user">
                        <div className="chat-bubble chat-bubble-user">
                          <p className="chat-text">{m.text}</p>
                          <span className="chat-time">{time(m)}</span>
                        </div>
                      </div>
                    );
                  }
                  const meta = m.meta;
                  return (
                    <div key={m.id} className="chat-row chat-row-bot">
                      <div className={`chat-bubble chat-bubble-bot${meta?.diagnosis ? " chat-bubble-wide" : ""}`}>
                        {meta?.kind === "diagnosis" && meta.diagnosis ? (
                          <DiagnosisCard diagnosis={meta.diagnosis} />
                        ) : (
                          <p className="chat-text">{m.text}</p>
                        )}

                        {isLast && meta?.kind === "question" && meta.question && (
                          <div className="chat-chips" aria-label="Варианты ответа">
                            {meta.question.options.map((o) => (
                              <button
                                key={o.value}
                                type="button"
                                className="chat-chip chat-chip-answer"
                                disabled={sending}
                                onClick={() => answer(meta.question!.symptom, o.value, o.label)}
                              >
                                {o.label}
                              </button>
                            ))}
                          </div>
                        )}

                        {isLast && meta?.suggestions && meta.suggestions.length > 0 && (
                          <div className="chat-chips" aria-label="Подсказки">
                            {meta.suggestions.map((s) => (
                              <button
                                key={s.text}
                                type="button"
                                className="chat-chip"
                                disabled={sending}
                                onClick={() => void submit({ text: s.text }, s.label)}
                              >
                                {s.label}
                              </button>
                            ))}
                          </div>
                        )}
                        <span className="chat-time">{time(m)}</span>
                      </div>
                    </div>
                  );
                })}

                {sending && (
                  <div className="chat-row chat-row-bot" aria-hidden="true">
                    <div className="chat-bubble chat-bubble-bot chat-typing">Думаю…</div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}

            {error && (
              <div className="pf-notice pf-notice-error" role="alert">
                {error}
              </div>
            )}

            <form className="chat-form" onSubmit={handleSubmit}>
              <input
                type="text"
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                maxLength={500}
                placeholder="Опишите проблему или задайте вопрос"
                aria-label="Сообщение"
                disabled={!loaded || sending}
              />
              <button type="submit" className="chat-send" disabled={!loaded || sending || !input.trim()}>
                Отправить
              </button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}
