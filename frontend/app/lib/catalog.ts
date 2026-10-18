// Запросы к каталогу. Используются в серверных компонентах (страницы /search и /plants/[id]).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Category = {
  id: number;
  name: string;
  image_url: string;
};

export type PlantListItem = {
  id: number;
  name: string;
  scientific_name: string | null;
  description: string | null;
  image_url: string | null;
  category: Category;
};

export type PlantDetail = PlantListItem & {
  optimal_lux: number | null;
  optimal_humidity: number | null;
  soil_composition: string | null;
  growth_duration_days: number | null;
  external_id: number | null;
  image_license: string | null;
  watering: string | null;
  watering_min_days: number | null;
  watering_max_days: number | null;
  sunlight: string[] | null;
  indoor: boolean | null;
  poisonous_to_pets: boolean | null;
  care_level: string | null;
};

export type PlantListResponse = {
  items: PlantListItem[];
  total: number;
  limit: number;
  offset: number;
};



export class CatalogError extends Error {}

async function apiFetch(path: string): Promise<Response> {
  try {
    // no-store: каталог всегда актуален, страницы не кэшируются на сервере
    return await fetch(`${API_URL}${path}`, { cache: "no-store" });
  } catch {
    throw new CatalogError("Не удалось связаться с сервером. Проверьте, что бэкенд запущен.");
  }
}

export async function getCategories(): Promise<Category[]> {
  const res = await apiFetch("/categories");
  if (!res.ok) throw new CatalogError("Не удалось загрузить категории.");
  return res.json();
}

export async function searchPlants(params: {
  q?: string;
  categoryId?: number;
  limit?: number;
  offset?: number;
}): Promise<PlantListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.categoryId) sp.set("category_id", String(params.categoryId));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));

  const res = await apiFetch(`/plants?${sp.toString()}`);
  if (!res.ok) throw new CatalogError("Не удалось загрузить список растений.");
  return res.json();
}

/** Возвращает null, если растения с таким id нет. */
export async function getPlant(id: number): Promise<PlantDetail | null> {
  const res = await apiFetch(`/plants/${id}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new CatalogError("Не удалось загрузить растение.");
  return res.json();
}

/** Склонение: plural(5, "растение", "растения", "растений") → "растений" */
export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}
