"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import SiteHeader from "@/app/components/SiteHeader";
import { checkAnswer, CourseError, getTest, type CheckResult, type TestData } from "@/app/lib/courses";

const LETTERS = ["А", "Б", "В", "Г", "Д"];

export default function CourseTestPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";

  const [data, setData] = useState<TestData | null>(null);
  const [loadError, setLoadError] = useState("");
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [wrong, setWrong] = useState<Record<string, string>>({}); // неверные варианты текущего вопроса и их объяснения
  const [result, setResult] = useState<CheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [attempts, setAttempts] = useState<Record<string, number>>({}); // сколько раз проверяли каждый вопрос
  const [finished, setFinished] = useState(false);

  const cardRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    getTest(slug)
      .then((t) => {
        if (!cancelled) setData(t);
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError(
          e instanceof CourseError && e.status === 404
            ? "Тест не найден."
            : e instanceof Error
              ? e.message
              : "Не удалось загрузить тест.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // К новому вопросу: прокрутка к началу карточки
  useEffect(() => {
    cardRef.current?.scrollIntoView?.({ block: "start" });
  }, [index, finished]);

  // К объяснению: фокус, чтобы его озвучили программы чтения с экрана
  useEffect(() => {
    if (result) feedbackRef.current?.focus();
  }, [result]);

  const questions = data?.questions ?? [];
  const question = questions[index];
  const total = questions.length;
  const solved = result?.correct === true;

  function select(optionId: string) {
    if (checking || solved || wrong[optionId]) return;
    setSelected(optionId);
    setResult(null);
    setError("");
  }

  async function check() {
    if (!question || !selected || checking) return;
    setChecking(true);
    setError("");
    try {
      const res = await checkAnswer(slug, question.id, selected);
      setAttempts((a) => ({ ...a, [question.id]: (a[question.id] ?? 0) + 1 }));
      if (!res.correct) setWrong((w) => ({ ...w, [selected]: res.feedback }));
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось проверить ответ. Попробуйте ещё раз.");
    } finally {
      setChecking(false);
    }
  }

  function retry() {
    setSelected(null);
    setResult(null);
  }

  function next() {
    if (index + 1 >= total) {
      setFinished(true);
      return;
    }
    setIndex(index + 1);
    setSelected(null);
    setResult(null);
    setWrong({});
  }

  function restart() {
    setIndex(0);
    setSelected(null);
    setResult(null);
    setWrong({});
    setAttempts({});
    setFinished(false);
  }

  const backLink = (
    <Link href={`/courses/${slug}`} className="crs-back">
      ← К конспекту
    </Link>
  );

  return (
    <div className="crs-page">
      <SiteHeader />

      <main className="crs-main crs-main-narrow">
        {backLink}

        {loadError && (
          <div className="crs-notice crs-notice-error" role="alert">
            {loadError}
          </div>
        )}

        {!loadError && !data && <p className="crs-muted">Загружаем тест…</p>}

        {data && finished && (
          <section className="crs-result" ref={cardRef} aria-labelledby="crs-result-title">
            {(() => {
              const firstTry = questions.filter((q) => attempts[q.id] === 1).length;
              const totalAttempts = Object.values(attempts).reduce((a, b) => a + b, 0);
              const retried = questions.filter((q) => (attempts[q.id] ?? 0) > 1);
              return (
                <>
                  <h1 id="crs-result-title" className="crs-title">
                    Тест пройден
                  </h1>
                  <p className="crs-result-score">
                    С первой попытки верно: <strong>{firstTry}</strong> из {total}
                  </p>
                  <p className="crs-muted">Всего ответов проверено: {totalAttempts}</p>
                  {retried.length > 0 ? (
                    <>
                      <h2 className="crs-sub">Темы, которые стоит повторить</h2>
                      <ul className="crs-retry-list">
                        {retried.map((q) => (
                          <li key={q.id}>
                            <strong>{q.topic}</strong>: попыток {attempts[q.id]}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="crs-note-ok">Все вопросы решены с первой попытки. Отличный результат!</p>
                  )}
                  <div className="crs-actions">
                    <button type="button" className="crs-btn" onClick={restart}>
                      Пройти заново
                    </button>
                    <Link href={`/courses/${slug}`} className="crs-btn crs-btn-ghost">
                      Перечитать конспект
                    </Link>
                    <Link href="/courses" className="crs-btn crs-btn-ghost">
                      Все курсы
                    </Link>
                  </div>
                </>
              );
            })()}
          </section>
        )}

        {data && !finished && question && (
          <section ref={cardRef} className="crs-question" aria-labelledby="crs-question-title">
            <div className="crs-progress">
              <span className="crs-progress-label">
                Вопрос {index + 1} из {total}
              </span>
              <div className="crs-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={index + (solved ? 1 : 0)}>
                <div className="crs-progress-fill" style={{ width: `${((index + (solved ? 1 : 0)) / total) * 100}%` }} />
              </div>
            </div>

            <span className="crs-tag">{question.topic}</span>
            {question.situation && <p className="crs-situation">{question.situation}</p>}
            <h1 id="crs-question-title" className="crs-question-text">
              {question.question}
            </h1>

            <div role="radiogroup" aria-labelledby="crs-question-title" className="crs-options">
              {question.options.map((o, i) => {
                const isWrong = Boolean(wrong[o.id]);
                const isCorrect = solved && selected === o.id;
                const showFeedback = isWrong && !(result && !result.correct && selected === o.id);
                const cls = ["crs-option", selected === o.id ? "crs-option-selected" : "", isWrong ? "crs-option-wrong" : "", isCorrect ? "crs-option-correct" : ""]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <div key={o.id}>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={selected === o.id}
                      className={cls}
                      disabled={checking || solved || isWrong}
                      onClick={() => select(o.id)}
                    >
                      <span className="crs-option-letter" aria-hidden="true">
                        {LETTERS[i] ?? i + 1}
                      </span>
                      <span className="crs-option-text">{o.text}</span>
                      {isWrong && <span className="crs-option-mark">не подходит</span>}
                      {isCorrect && <span className="crs-option-mark crs-option-mark-ok">верно</span>}
                    </button>
                    {showFeedback && <p className="crs-option-feedback">{wrong[o.id]}</p>}
                  </div>
                );
              })}
            </div>

            <div className="crs-live" aria-live="polite">
              {result && (
                <div
                  ref={feedbackRef}
                  tabIndex={-1}
                  className={`crs-feedback ${result.correct ? "crs-feedback-ok" : "crs-feedback-bad"}`}
                >
                  <p className="crs-feedback-title">{result.correct ? "Верно!" : "Неверно"}</p>
                  <p>{result.feedback}</p>
                </div>
              )}
              {error && (
                <div className="crs-notice crs-notice-error" role="alert">
                  {error}
                </div>
              )}
            </div>

            <div className="crs-actions">
              {!result && (
                <button type="button" className="crs-btn" onClick={check} disabled={!selected || checking}>
                  {checking ? "Проверяем…" : "Проверить ответ"}
                </button>
              )}
              {result && !result.correct && (
                <button type="button" className="crs-btn" onClick={retry}>
                  Попробовать ещё раз
                </button>
              )}
              {solved && (
                <button type="button" className="crs-btn" onClick={next}>
                  {index + 1 >= total ? "Завершить тест" : "Следующий вопрос"}
                </button>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
