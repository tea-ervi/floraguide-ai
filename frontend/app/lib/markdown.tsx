// Мини-разбор Markdown для конспектов: заголовки ##/###, абзацы, списки, цитаты, **жирный**, *курсив*.
// Текст превращается в React-элементы, а не в HTML-строку, поэтому вставить в страницу чужой код нельзя.
import type { ReactNode } from "react";

export type Heading = { id: string; text: string };

type Block =
  | { type: "h2"; id: string; text: string }
  | { type: "h3"; text: string }
  | { type: "p"; text: string }
  | { type: "quote"; text: string }
  | { type: "ul" | "ol"; items: string[] };

function parse(source: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: { type: "ul" | "ol"; items: string[] } | null = null;
  let h2Count = 0;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "p", text: paragraph.join(" ") });
    paragraph = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const raw of source.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    const h2 = line.match(/^##\s+(.+)$/);
    const h3 = line.match(/^###\s+(.+)$/);
    const ul = line.match(/^[-*]\s+(.+)$/);
    const ol = line.match(/^\d+\.\s+(.+)$/);
    const quote = line.match(/^>\s?(.*)$/);
    if (h2 || h3 || ul || ol || quote) flushParagraph();
    if (!ul && !ol) flushList();

    if (h2) blocks.push({ type: "h2", id: `section-${++h2Count}`, text: h2[1] });
    else if (h3) blocks.push({ type: "h3", text: h3[1] });
    else if (ul || ol) {
      const type = ul ? "ul" : "ol";
      if (list && list.type !== type) flushList();
      list = list ?? { type, items: [] };
      list.items.push((ul ?? ol)![1]);
    } else if (quote) blocks.push({ type: "quote", text: quote[1] });
    else paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

export function extractHeadings(source: string): Heading[] {
  return parse(source).flatMap((b) => (b.type === "h2" ? [{ id: b.id, text: b.text }] : []));
}

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    return part;
  });
}

export function Markdown({ text }: { text: string }) {
  return (
    <>
      {parse(text).map((b, i) => {
        switch (b.type) {
          case "h2":
            return <h2 key={i} id={b.id}>{inline(b.text)}</h2>;
          case "h3":
            return <h3 key={i}>{inline(b.text)}</h3>;
          case "p":
            return <p key={i}>{inline(b.text)}</p>;
          case "quote":
            return <blockquote key={i}>{inline(b.text)}</blockquote>;
          case "ul":
            return <ul key={i}>{b.items.map((item, j) => <li key={j}>{inline(item)}</li>)}</ul>;
          case "ol":
            return <ol key={i}>{b.items.map((item, j) => <li key={j}>{inline(item)}</li>)}</ol>;
        }
      })}
    </>
  );
}
