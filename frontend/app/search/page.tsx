import Link from "next/link";
import { redirect } from "next/navigation";
import PlantCard from "../components/PlantCard";
import SiteHeader from "../components/SiteHeader";
import {
  CatalogError,
  getCategories,
  plural,
  searchPlants,
  type Category,
  type PlantListResponse,
} from "../lib/catalog";

export const metadata = { title: "Каталог растений — FloraGuide" };

const PAGE_SIZE = 12;

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function buildHref(q: string, category: number | undefined, page: number): string {
  const sp = new URLSearchParams();
  if (q) sp.set("q", q);
  if (category) sp.set("category", String(category));
  if (page > 1) sp.set("page", String(page));
  const qs = sp.toString();
  return qs ? `/search?${qs}` : "/search";
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;

  const q = first(sp.q).trim().slice(0, 100);
  const categoryRaw = Number.parseInt(first(sp.category), 10);
  const category = Number.isInteger(categoryRaw) && categoryRaw > 0 ? categoryRaw : undefined;
  const page = Math.max(1, Number.parseInt(first(sp.page), 10) || 1);

  let categories: Category[] = [];
  let data: PlantListResponse | null = null;
  let error = "";

  try {
    [categories, data] = await Promise.all([
      getCategories(),
      searchPlants({
        q: q || undefined,
        categoryId: category,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    ]);
  } catch (e) {
    error = e instanceof CatalogError ? e.message : "Что-то пошло не так. Попробуйте позже.";
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  // Страница за пределами диапазона (например, после удаления данных): уходим на последнюю
  if (data && data.total > 0 && page > totalPages) {
    redirect(buildHref(q, category, totalPages));
  }

  return (
    <div className="cat-page">
      <SiteHeader />

      <main className="cat-main">
        <h1 className="cat-title">{q ? `Результаты по запросу «${q}»` : "Каталог растений"}</h1>

        <form action="/search" role="search" className="cat-search">
          <input
            type="search"
            name="q"
            defaultValue={q}
            maxLength={100}
            placeholder="Название растения или описание"
            aria-label="Поиск растений"
            className="cat-search-input"
          />
          {category && <input type="hidden" name="category" value={category} />}
          <button type="submit" className="cat-search-btn">
            Найти
          </button>
        </form>

        {categories.length > 0 && (
          <nav className="cat-chips" aria-label="Категории">
            <Link
              href={buildHref(q, undefined, 1)}
              className="cat-chip"
              aria-current={!category ? "true" : undefined}
            >
              Все
            </Link>
            {categories.map((c) => (
              <Link
                key={c.id}
                href={buildHref(q, c.id, 1)}
                className="cat-chip"
                aria-current={category === c.id ? "true" : undefined}
              >
                {c.name}
              </Link>
            ))}
          </nav>
        )}

        {error && (
          <div className="cat-notice cat-notice-error" role="alert">
            {error}
          </div>
        )}

        {data && data.total === 0 && (
          <div className="cat-notice">
            <p>Ничего не найдено. Попробуйте изменить запрос или выбрать другую категорию.</p>
            {(q || category) && (
              <Link href="/search" className="cat-link">
                Сбросить поиск и фильтры
              </Link>
            )}
          </div>
        )}

        {data && data.total > 0 && (
          <>
            <p className="cat-count">
              Найдено: {data.total} {plural(data.total, "растение", "растения", "растений")}
            </p>

            <ul className="cat-grid">
              {data.items.map((plant) => (
                <PlantCard key={plant.id} plant={plant} />
              ))}
            </ul>

            {totalPages > 1 && (
              <nav className="cat-pagination" aria-label="Страницы">
                {page > 1 ? (
                  <Link href={buildHref(q, category, page - 1)} rel="prev" className="cat-page-btn">
                    ← Назад
                  </Link>
                ) : (
                  <span className="cat-page-btn cat-page-btn-disabled" aria-disabled="true">
                    ← Назад
                  </span>
                )}

                <span className="cat-page-info">
                  Страница {page} из {totalPages}
                </span>

                {page < totalPages ? (
                  <Link href={buildHref(q, category, page + 1)} rel="next" className="cat-page-btn">
                    Вперёд →
                  </Link>
                ) : (
                  <span className="cat-page-btn cat-page-btn-disabled" aria-disabled="true">
                    Вперёд →
                  </span>
                )}
              </nav>
            )}
          </>
        )}
      </main>
    </div>
  );
}
