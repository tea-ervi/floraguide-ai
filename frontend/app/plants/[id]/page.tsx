import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import SiteHeader from "@/app/components/SiteHeader";
import { CatalogError, getPlant, plural, type PlantDetail } from "@/app/lib/catalog";

type Props = { params: Promise<{ id: string }> };


function parseId(raw: string): number | null {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/** 365 → «около 1 года», 180 → «около 6 мес.», 45 → «45 дн.» */
function formatDuration(days: number): string {
  if (days < 60) return `${days} ${plural(days, "день", "дня", "дней")}`;
  if (days < 365) return `около ${Math.round(days / 30)} мес.`;
  const years = Math.round(days / 365);
  return `около ${years} ${plural(years, "года", "лет", "лет")}`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const plantId = parseId(id);
  if (!plantId) return { title: "Растение не найдено — FloraGuide" };
  try {
    const plant = await getPlant(plantId);
    return { title: plant ? `${plant.name} — FloraGuide` : "Растение не найдено — FloraGuide" };
  } catch {
    return { title: "FloraGuide" };
  }
}

export default async function PlantPage({ params }: Props) {
  const { id } = await params;
  const plantId = parseId(id);
  if (!plantId) notFound();

  let plant: PlantDetail | null = null;
  let error = "";
  try {
    plant = await getPlant(plantId);
  } catch (e) {
    error = e instanceof CatalogError ? e.message : "Что-то пошло не так. Попробуйте позже.";
  }

  if (!error && !plant) notFound();

  return (
    <div className="cat-page">
      <SiteHeader />

      <main className="cat-main">
        {error || !plant ? (
          <div className="cat-notice cat-notice-error" role="alert">
            {error}
          </div>
        ) : (
          <article>
            <nav className="cat-breadcrumbs" aria-label="Навигация">
              <Link href="/search">Каталог</Link>
              <span aria-hidden="true">/</span>
              <Link href={`/search?category=${plant.category.id}`}>{plant.category.name}</Link>
              <span aria-hidden="true">/</span>
              <span aria-current="page">{plant.name}</span>
            </nav>

            <header className="cat-plant-head">
              <span className="cat-tag">{plant.category.name}</span>
              <h1 className="cat-title">{plant.name}</h1>
              {plant.scientific_name && <p className="cat-plant-latin">{plant.scientific_name}</p>}
            </header>

            {plant.description && <p className="cat-plant-desc">{plant.description}</p>}

            <h2 className="cat-section-title">Условия содержания</h2>
            <dl className="cat-facts">
              <div className="cat-fact">
                <dt>Освещённость</dt>
                <dd>{plant.optimal_lux != null ? `≈ ${plant.optimal_lux} лк` : "—"}</dd>
              </div>
              <div className="cat-fact">
                <dt>Влажность воздуха</dt>
                <dd>{plant.optimal_humidity != null ? `${plant.optimal_humidity} %` : "—"}</dd>
              </div>
              <div className="cat-fact">
                <dt>Срок роста</dt>
                <dd>
                  {plant.growth_duration_days != null
                    ? formatDuration(plant.growth_duration_days)
                    : "—"}
                </dd>
              </div>
              <div className="cat-fact cat-fact-wide">
                <dt>Грунт</dt>
                <dd>{plant.soil_composition ?? "—"}</dd>
              </div>
            </dl>

            <div className="cat-actions">
              <button type="button" className="cat-add-btn" disabled>
                Добавить в мои растения
              </button>
              <p className="cat-actions-note">Эта функция появится в ближайшее время.</p>
            </div>
          </article>
        )}
      </main>
    </div>
  );
}
