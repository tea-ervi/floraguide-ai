import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AddToProfileButton from "@/app/components/AddToProfileButton";
import SiteHeader from "@/app/components/SiteHeader";
import { CatalogError, getPlant, plural, type PlantDetail } from "@/app/lib/catalog";
import { suggestedIntervalDays } from "@/app/lib/watering";

type Props = { params: Promise<{ id: string }> };

type Fact = { label: string; value: string; wide?: boolean };

const WATERING_LABELS: Record<string, string> = {
  frequent: "Частый",
  average: "Умеренный",
  minimum: "Редкий",
  none: "Почти не требуется",
};

const SUNLIGHT_LABELS: Record<string, string> = {
  "full sun": "прямое солнце",
  "part shade": "полутень",
  "part sun/part shade": "солнце и полутень",
  "sun-part shade": "солнце и полутень",
  "filtered shade": "рассеянный свет",
  "full shade": "тень",
};

const CARE_LABELS: Record<string, string> = {
  low: "Низкая сложность",
  medium: "Средняя сложность",
  high: "Высокая сложность",
};

/** «Название (https://...)» → ссылка на лицензию; если формат другой, показывает текст как есть. */
function LicenseText({ value }: { value: string }) {
  const match = value.match(/^(.*?)\s*\((https?:\/\/[^\s)]+)\)\s*$/);
  if (!match || !match[1]) return <>{value}</>;
  return (
    <a href={match[2]} target="_blank" rel="noopener noreferrer">
      {match[1]}
    </a>
  );
}

function parseId(raw: string): number | null {
  const n = Number(raw);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/** 365 → «около 1 года», 180 → «около 6 мес.», 45 → «45 дней» */
function formatDuration(days: number): string {
  if (days < 60) return `${days} ${plural(days, "день", "дня", "дней")}`;
  if (days < 365) return `около ${Math.round(days / 30)} мес.`;
  const years = Math.round(days / 365);
  return `около ${years} ${plural(years, "года", "лет", "лет")}`;
}

function wateringText(plant: PlantDetail): string | null {
  const label = plant.watering ? (WATERING_LABELS[plant.watering.toLowerCase()] ?? plant.watering) : null;
  const min = plant.watering_min_days;
  const max = plant.watering_max_days ?? min;
  let days: string | null = null;
  if (min != null && max != null) {
    days =
      min === max
        ? `каждые ${min} ${plural(min, "день", "дня", "дней")}`
        : `каждые ${min}–${max} ${plural(max, "день", "дня", "дней")}`;
  }
  if (label && days) return `${label} · ${days}`;
  return label ?? days;
}

function buildFacts(plant: PlantDetail): Fact[] {
  const facts: Fact[] = [];

  const watering = wateringText(plant);
  if (watering) facts.push({ label: "Полив", value: watering });

  if (plant.sunlight && plant.sunlight.length > 0) {
    const text = plant.sunlight.map((s) => SUNLIGHT_LABELS[s.toLowerCase()] ?? s).join(", ");
    facts.push({ label: "Освещение", value: text });
  }
  if (plant.optimal_lux != null) facts.push({ label: "Освещённость", value: `≈ ${plant.optimal_lux} лк` });
  if (plant.optimal_humidity != null) facts.push({ label: "Влажность воздуха", value: `${plant.optimal_humidity} %` });
  if (plant.growth_duration_days != null)
    facts.push({ label: "Срок роста", value: formatDuration(plant.growth_duration_days) });
  if (plant.care_level)
    facts.push({ label: "Сложность ухода", value: CARE_LABELS[plant.care_level.toLowerCase()] ?? plant.care_level });
  if (plant.poisonous_to_pets != null)
    facts.push({
      label: "Домашние животные",
      value: plant.poisonous_to_pets ? "Токсично для питомцев" : "Не отмечено как токсичное",
    });
  if (plant.soil_composition) facts.push({ label: "Грунт", value: plant.soil_composition, wide: true });

  return facts;
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

  const facts = plant ? buildFacts(plant) : [];
  const suggested = suggestedIntervalDays(plant?.watering_min_days ?? null, plant?.watering_max_days ?? null);

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

            <div className={plant.image_url ? "cat-plant-layout" : undefined}>
              <div>
                <header className="cat-plant-head">
                  <span className="cat-tag">{plant.category.name}</span>
                  <h1 className="cat-title">{plant.name}</h1>
                  {plant.scientific_name && <p className="cat-plant-latin">{plant.scientific_name}</p>}
                </header>

                {plant.description && <p className="cat-plant-desc">{plant.description}</p>}
              </div>

              {plant.image_url && (
                <figure className="cat-plant-photo">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={plant.image_url} alt={plant.name} />
                  {plant.image_license && (
                    <figcaption className="cat-photo-credit">
                      Фото: Perenual, <LicenseText value={plant.image_license} />
                    </figcaption>
                  )}
                </figure>
              )}
            </div>

            {plant.poisonous_to_pets === true && (
              <div className="cat-warning" role="note">
                <strong>Осторожно:</strong> растение токсично для домашних животных. Держите его вне их
                досягаемости.
              </div>
            )}

            <h2 className="cat-section-title">Условия содержания</h2>
            {facts.length > 0 ? (
              <dl className="cat-facts">
                {facts.map((f) => (
                  <div key={f.label} className={f.wide ? "cat-fact cat-fact-wide" : "cat-fact"}>
                    <dt>{f.label}</dt>
                    <dd>{f.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="cat-actions-note">Данные об уходе за этим растением пока не добавлены.</p>
            )}

            {plant.external_id != null && (
              <p className="cat-actions-note">Данные об уходе получены из открытого API Perenual.</p>
            )}

            <div className="cat-actions">
              <AddToProfileButton plantId={plant.id} suggestedDays={suggested.days} fromSpecies={suggested.fromSpecies} />
            </div>
          </article>
        )}
      </main>
    </div>
  );
}
