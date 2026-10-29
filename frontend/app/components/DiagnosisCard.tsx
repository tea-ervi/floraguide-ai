import type { Diagnosis } from "../lib/chat";

const URGENCY = {
  high: { label: "Срочно", cls: "chat-badge-high" },
  medium: { label: "В ближайшие дни", cls: "chat-badge-medium" },
  low: { label: "Не срочно", cls: "chat-badge-low" },
} as const;

export default function DiagnosisCard({ diagnosis }: { diagnosis: Diagnosis }) {
  const urgency = URGENCY[diagnosis.urgency] ?? URGENCY.low;

  return (
    <div className="chat-diag">
      <div className="chat-diag-head">
        <h3 className="chat-diag-title">
          {diagnosis.confident ? "Скорее всего: " : "Возможная причина: "}
          {diagnosis.name}
        </h3>
        <span className={`chat-badge ${urgency.cls}`}>{urgency.label}</span>
      </div>

      <div className="chat-conf" role="img" aria-label={`Уверенность ${diagnosis.confidence}%`}>
        <div className="chat-conf-track">
          <div className="chat-conf-fill" style={{ width: `${diagnosis.confidence}%` }} />
        </div>
        <span className="chat-conf-value">{diagnosis.confidence}%</span>
      </div>

      {!diagnosis.confident && (
        <p className="chat-note">Данных пока недостаточно: опишите подробнее или ответьте на вопросы.</p>
      )}

      <p className="chat-diag-summary">{diagnosis.summary}</p>

      {diagnosis.why.length > 0 && (
        <section>
          <h4 className="chat-diag-sub">Почему я так считаю</h4>
          <ul className="chat-list">
            {diagnosis.why.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {diagnosis.against.length > 0 && (
        <section>
          <h4 className="chat-diag-sub">Что говорит против</h4>
          <ul className="chat-list">
            {diagnosis.against.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h4 className="chat-diag-sub">Что делать</h4>
        <ol className="chat-list chat-steps">
          {diagnosis.steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </section>

      {diagnosis.alternatives.length > 0 && (
        <p className="chat-alt">
          Также возможно:{" "}
          {diagnosis.alternatives.map((a) => `${a.name} (${a.confidence}%)`).join(", ")}.
        </p>
      )}

      {diagnosis.sources.length > 0 && (
        <p className="chat-sources">
          Источники:{" "}
          {diagnosis.sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ", "}
              <a href={s.url} target="_blank" rel="noopener noreferrer">
                {s.title}
              </a>
            </span>
          ))}
        </p>
      )}

      <p className="chat-disclaimer">Это подсказка по описанию, а не замена осмотра растения.</p>
    </div>
  );
}
