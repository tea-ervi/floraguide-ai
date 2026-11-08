import type { Metadata } from "next";
import Link from "next/link";
import SiteHeader from "@/app/components/SiteHeader";
import { CourseError, getCourses, type CourseSummary } from "@/app/lib/courses";

export const metadata: Metadata = {
  title: "Курсы — FloraGuide",
  description: "Короткие курсы по выращиванию растений, овощей, фруктов и грибов с тестами на понимание.",
};

// Темы курсов. Появятся новые курсы по овощам и фруктам, и они сразу попадут в свой раздел.
const TOPICS = [
  { id: "plants", label: "Растения" },
  { id: "vegetables", label: "Овощи и фрукты" },
  { id: "mushrooms", label: "Грибы" },
];

type Props = { searchParams: Promise<{ topic?: string | string[] }> };

export default async function CoursesPage({ searchParams }: Props) {
  const sp = await searchParams;
  const topicParam = Array.isArray(sp.topic) ? sp.topic[0] : sp.topic;
  const topic = TOPICS.some((t) => t.id === topicParam) ? topicParam : undefined;

  let courses: CourseSummary[] = [];
  let error = "";
  try {
    courses = await getCourses();
  } catch (e) {
    error = e instanceof CourseError ? e.message : "Что-то пошло не так. Попробуйте позже.";
  }

  const visible = topic ? courses.filter((c) => c.topic === topic) : courses;
  const count = (id: string) => courses.filter((c) => c.topic === id).length;

  return (
    <div className="crs-page">
      <SiteHeader />

      <main className="crs-main">
        <h1 className="crs-title">Курсы</h1>
        <p className="crs-lead">
          Короткие конспекты и тесты на понимание причин и следствий: не заучивание, а умение понять, что произошло и
          почему.
        </p>

        <nav className="crs-chips" aria-label="Темы курсов">
          <Link href="/courses" className="crs-chip" aria-current={!topic ? "true" : undefined}>
            Все ({courses.length})
          </Link>
          {TOPICS.map((t) => (
            <Link key={t.id} href={`/courses?topic=${t.id}`} className="crs-chip" aria-current={topic === t.id ? "true" : undefined}>
              {t.label} ({count(t.id)})
            </Link>
          ))}
        </nav>

        {error && (
          <div className="crs-notice crs-notice-error" role="alert">
            {error}
          </div>
        )}

        {!error && visible.length === 0 && (
          <div className="crs-notice">
            <p>В этой теме курсов пока нет, они скоро появятся.</p>
            <Link href="/courses" className="crs-link">
              Показать все курсы
            </Link>
          </div>
        )}

        {visible.length > 0 && (
          <ul className="crs-grid">
            {visible.map((c) => (
              <li key={c.slug}>
                <Link href={`/courses/${c.slug}`} className="crs-card">
                  <span className="crs-tag">{c.topic_label}</span>
                  <h2 className="crs-card-title">{c.title}</h2>
                  <p className="crs-card-desc">{c.description}</p>
                  <p className="crs-meta">
                    <span>{c.level}</span>
                    <span>{c.duration_minutes} мин</span>
                    <span>тест: {c.questions_count} вопросов</span>
                  </p>
                  <span className="crs-card-cta">Открыть курс →</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
