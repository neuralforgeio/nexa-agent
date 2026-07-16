"use client";

import ReactMarkdown from "react-markdown";
import { Check, Copy } from "lucide-react";
import { useState } from "react";

export function Markdown({ content }: { content: string }) {
  return (
    <div className="nexa-markdown">
      <ReactMarkdown
        components={{
          code({ className, children, ...props }) {
            const isBlock = /language-/.test(className ?? "");
            if (!isBlock) {
              return (
                <code
                  className="rounded bg-tertiary px-1.5 py-0.5 font-mono text-[0.85em] text-primary"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            const lang = (className ?? "").replace("language-", "") || "code";
            return <CodeBlock lang={lang}>{String(children).replace(/\n$/, "")}</CodeBlock>;
          },
          pre({ children }) {
            return <>{children}</>;
          },
          a({ children, ...props }) {
            return (
              <a
                className="text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
                target="_blank"
                rel="noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
          ul({ children }) {
            return <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>;
          },
          h1({ children }) {
            return <h1 className="mb-2 mt-4 text-lg font-semibold first:mt-0">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="mb-2 mt-3 text-base font-semibold first:mt-0">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="mb-1.5 mt-2 text-[15px] font-semibold first:mt-0">{children}</h3>;
          },
          p({ children }) {
            return <p className="my-2 first:mt-0 last:mb-0">{children}</p>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-2 border-l-2 border-primary/40 pl-3 text-secondary italic">
                {children}
              </blockquote>
            );
          },
          table({ children }) {
            return (
              <div className="nexa-scroll my-3 overflow-x-auto">
                <table className="w-full border-collapse text-[13px]">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border border-border bg-tertiary px-2.5 py-1.5 text-left font-semibold">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="border border-border px-2.5 py-1.5">{children}</td>;
          },
          hr() {
            return <hr className="my-4 border-border" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ lang, children }: { lang: string; children: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="nexa-scroll my-3 overflow-hidden rounded-lg border border-border bg-secondary">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="font-mono text-[11px] text-tertiary">{lang}</span>
        <button
          onClick={() => {
            navigator.clipboard.writeText(children);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-tertiary transition-colors hover:bg-tertiary hover:text-foreground"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-success" />
              <span className="text-success">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="nexa-scroll overflow-x-auto p-3.5 font-mono text-[13px] leading-relaxed text-foreground/90">
        <code>{children}</code>
      </pre>
    </div>
  );
}
