import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import SiteHeader from "@/app/components/SiteHeader";
import { CourseError, getCourse, type CourseDetail } from "@/app/lib/courses";
import { extractHeadings, Markdown } from "@/app/lib/markdown";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const course = await getCourse(slug);
    return { title: `${course.title} — Курсы FloraGuide`, description: course.description };
  } catch {
    return { title: "Курс — FloraGuide" };
  }
}

export default async function CoursePage({ params }: Props) {
  const { slug } = await params;

  let course: CourseDetail | null = null;
  let error = "";
  try {
    course = await getCourse(slug);
  } catch (e) {
    if (e instanceof CourseError && e.status === 404) notFound();
    error = e instanceof CourseError ? e.message : "Что-то пошло не так. Попробуйте позже.";
  }

  const headings = course ? extractHeadings(course.notes) : [];

  return (
    <div className="crs-page">
      <SiteHeader />

      <main className="crs-main">
        {error || !course ? (
          <div className="crs-notice crs-notice-error" role="alert">
            {error}
          </div>
        ) : (
          <article>
            <nav className="crs-breadcrumbs" aria-label="Навигация">
              <Link href="/courses">Курсы</Link>
              <span aria-hidden="true">/</span>
              <span aria-current="page">{course.title}</span>
            </nav>

            <header className="crs-head">
              <span className="crs-tag">{course.topic_label}</span>
              <h1 className="crs-title">{course.title}</h1>
              <p className="crs-lead">{course.description}</p>
              <p className="crs-meta">
                <span>{course.level}</span>
                <span>{course.duration_minutes} мин</span>
                <span>тест: {course.questions_count} вопросов</span>
              </p>
              <Link href={`/courses/${course.slug}/test`} className="crs-btn">
                Пройти тест
              </Link>
            </header>

            {headings.length > 0 && (
              <nav className="crs-toc" aria-label="Содержание">
                <h2 className="crs-toc-title">Содержание</h2>
                <ol>
                  {headings.map((h) => (
                    <li key={h.id}>
                      <a href={`#${h.id}`}>{h.text.replace(/^\d+\.\s*/, "")}</a>
                    </li>
                  ))}
                </ol>
              </nav>
            )}

            <div className="crs-notes">
              <Markdown text={course.notes} />
            </div>

            <section className="crs-test-cta" aria-labelledby="crs-test-cta-title">
              <h2 id="crs-test-cta-title">Проверьте, как вы поняли материал</h2>
              <p>
                В тесте {course.questions_count} вопросов. Это не пересказ конспекта: в каждом описана ситуация, и нужно понять,
                что в ней происходит и почему. Если ответ неверный, вы увидите объяснение и сможете попробовать ещё раз.
              </p>
              <Link href={`/courses/${course.slug}/test`} className="crs-btn">
                Начать тест
              </Link>
            </section>

            {course.sources.length > 0 && (
              <section className="crs-sources" aria-labelledby="crs-sources-title">
                <h2 id="crs-sources-title">Источники</h2>
                <p>Конспект написан своими словами по этим материалам. Подробности и точные значения смотрите в них.</p>
                <ul>
                  {course.sources.map((s) => (
                    <li key={s.url}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer">
                        {s.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </article>
        )}
      </main>
    </div>
  );
}
