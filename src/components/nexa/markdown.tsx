"use client";

import ReactMarkdown from "react-markdown";
import { Check, Copy } from "lucide-react";
import { useState } from "react";

/**
 * Markdown renderer tuned for terminal aesthetics. Adds a copy button to
 * code blocks and styles lists/links inline.
 */
export function Markdown({ content }: { content: string }) {
  return (
    <div className="prose-nexa text-sm leading-relaxed">
      <ReactMarkdown
        components={{
          code({ className, children, ...props }) {
            const isBlock = /language-/.test(className ?? "");
            if (!isBlock) {
              return (
                <code
                  className="rounded bg-muted px-1.5 py-0.5 text-[0.85em] text-emerald-300"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return <CodeBlock>{String(children)}</CodeBlock>;
          },
          pre({ children }) {
            return <>{children}</>;
          },
          a({ children, ...props }) {
            return (
              <a
                className="text-emerald-400 underline decoration-dotted underline-offset-2 hover:text-emerald-300"
                target="_blank"
                rel="noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
          ul({ children }) {
            return <ul className="my-2 list-disc pl-5 space-y-1">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="my-2 list-decimal pl-5 space-y-1">{children}</ol>;
          },
          h1({ children }) {
            return <h1 className="mt-3 mb-2 text-base font-semibold text-foreground">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="mt-3 mb-2 text-sm font-semibold text-foreground">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="mt-2 mb-1 text-sm font-semibold text-foreground">{children}</h3>;
          },
          p({ children }) {
            return <p className="my-2 first:mt-0 last:mb-0">{children}</p>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-2 border-l-2 border-emerald-500/40 pl-3 text-muted-foreground italic">
                {children}
              </blockquote>
            );
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto nexa-scroll">
                <table className="w-full border-collapse text-xs">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return <th className="border border-border bg-muted/60 px-2 py-1 text-left font-semibold">{children}</th>;
          },
          td({ children }) {
            return <td className="border border-border px-2 py-1">{children}</td>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="group relative my-3 rounded-md border border-border bg-black/40">
      <button
        onClick={() => {
          navigator.clipboard.writeText(children);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
        className="absolute right-2 top-2 hidden rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground group-hover:block"
      >
        {copied ? <Check className="h-3 w-3 inline" /> : <Copy className="h-3 w-3 inline" />}
      </button>
      <pre className="overflow-x-auto nexa-scroll p-3 text-xs leading-relaxed text-emerald-200/90">
        <code>{children}</code>
      </pre>
    </div>
  );
}
