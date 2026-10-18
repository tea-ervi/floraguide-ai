import Link from "next/link";
import type { PlantListItem } from "../lib/catalog";

export default function PlantCard({ plant }: { plant: PlantListItem }) {
  return (
    <li>
      <Link href={`/plants/${plant.id}`} className="cat-card">
        <span className="cat-card-icon" aria-hidden="true">
          <svg width="26" height="26" viewBox="0 0 32 32">
            <path d="M6 26C6 13 14 5 27 5c0 13-8 21-21 21Z" fill="currentColor" />
            <path d="M6 26 20 12" stroke="#EEF4E8" strokeWidth="2" strokeLinecap="round" fill="none" />
          </svg>
        </span>
        <span className="cat-tag">{plant.category.name}</span>
        <h2 className="cat-card-title">{plant.name}</h2>
        {plant.scientific_name && <p className="cat-card-latin">{plant.scientific_name}</p>}
        {plant.description && <p className="cat-card-desc">{plant.description}</p>}
      </Link>
    </li>
  );
}
