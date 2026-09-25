import type { Components } from "react-markdown";

/**
 * Hand-styled markdown element mapping for coach_analysis + chat bubbles —
 * matches the dark/amber palette directly rather than fighting a packaged
 * typography plugin's own color assumptions.
 */
export const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mb-2 mt-4 text-base font-semibold text-ink first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1.5 mt-4 text-sm font-semibold text-ink first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-3 text-sm font-medium text-ink first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="mb-2 text-sm leading-relaxed text-ink last:mb-0">
      {children}
    </p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 list-disc space-y-0.5 pl-5 text-sm text-ink last:mb-0">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 list-decimal space-y-0.5 pl-5 text-sm text-ink last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-ink">{children}</strong>
  ),
  em: ({ children }) => <em className="text-ink-muted">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-amber underline-offset-2 hover:underline"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-slate-surface-raised px-1 py-0.5 font-mono text-[13px] text-amber">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-lg bg-slate-surface-raised p-3 font-mono text-[13px] text-ink last:mb-0">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-amber/40 pl-3 text-sm text-ink-muted last:mb-0">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-3 border-slate-border" />,
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-slate-border px-2 py-1 text-left font-medium text-ink-muted">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-slate-border/60 px-2 py-1 text-ink">
      {children}
    </td>
  ),
};
