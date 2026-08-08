/**
 * Nexa Agent — Markdown Renderer (v4.1.0)
 * ========================================
 *
 * Real Markdown rendering for assistant messages. Supports:
 *
 * - Headings (# to ######)
 * - Emphasis: **bold**, *italic*, ~~strikethrough~~, `inline code`
 * - Code blocks with syntax highlighting (rehype-highlight)
 * - Lists (ordered + unordered + checkbox)
 * - Tables
 * - Links (target="_blank" with rel="noopener noreferrer")
 * - Blockquotes, horizontal rules, and task lists (via remark-gfm)
 *
 * The component is intentionally standalone — any text-containing
 * surface (chat bubbles, scratchpad, tool results) can import it.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

interface MarkdownProps {
  children: string;
  /** Maximum height for embedded <pre> blocks; 0 = unlimited. */
  codeMaxHeight?: number;
}

export function Markdown({ children, codeMaxHeight = 320 }: MarkdownProps) {
  return (
    <div className="nexa-markdown" style={{ fontSize: 15, lineHeight: 1.7, color: "#ECECEC" }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // Headings
          h1: ({ children }) => (
            <h1 style={{ fontSize: 22, fontWeight: 700, margin: "16px 0 8px", color: "#ECECEC" }}>
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 style={{ fontSize: 18, fontWeight: 600, margin: "14px 0 6px", color: "#ECECEC" }}>
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 style={{ fontSize: 16, fontWeight: 600, margin: "12px 0 4px", color: "#ECECEC" }}>
              {children}
            </h3>
          ),
          // Paragraphs
          p: ({ children }) => (
            <p style={{ margin: "6px 0", lineHeight: 1.7, color: "#ECECEC" }}>{children}</p>
          ),
          // Inline code
          code: (props: any) => {
            const { inline, className, children } = props;
            if (inline) {
              return (
                <code
                  style={{
                    padding: "2px 6px",
                    borderRadius: 4,
                    background: "#1c1e22",
                    color    : "#CEE1FF",
                    fontSize: "0.9em",
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  }}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                className={className}
                style={{
                  display: "block",
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  fontSize: 13,
                  lineHeight: 1.6,
                }}
              >
                {children}
              </code>
            );
          },
          // Code blocks
          pre: ({ children }) => (
            <pre
              style={{
                background: "#0B0C0E",
                border: "1px solid #232428",
                borderRadius: 8,
                padding: "12px 14px",
                overflowX: "auto",
                overflowY: codeMaxHeight > 0 ? "auto" : undefined,
                maxHeight: codeMaxHeight > 0 ? codeMaxHeight : undefined,
                margin: "10px 0",
                fontSize: 13,
              }}
            >
              {children}
            </pre>
          ),
          // Lists
          ul: ({ children }) => (
            <ul style={{ margin: "6px 0", paddingLeft: 24, listStyleType: "disc" }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: "6px 0", paddingLeft: 24, listStyleType: "decimal" }}>{children}</ol>
          ),
          li: ({ children }) => (
            <li style={{ margin: "3px 0", lineHeight: 1.6 }}>{children}</li>
          ),
          // Blockquote
          blockquote: ({ children }) => (
            <blockquote
              style={{
                borderLeft: "3px solid #4A9EFF",
                paddingLeft: 14,
                marginLeft: 0,
                marginRight: 0,
                margin: "10px 0",
                color: "#9A9A9A",
                fontStyle: "italic",
              }}
            >
              {children}
            </blockquote>
          ),
          // Tables
          table: ({ children }) => (
            <div style={{ overflowX: "auto", margin: "10px 0" }}>
              <table
                style={{
                  borderCollapse: "collapse",
                  width: "100%",
                  fontSize: 13,
                  border: "1px solid #2E2F34",
                }}
              >
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead style={{ background: "#141618", borderBottom: "1px solid #2E2F34" }}>
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th
              style={{
                padding: "8px 12px",
                textAlign: "left",
                fontWeight: 600,
                color: "#ECECEC",
                borderRight: "1px solid #2E2F34",
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              style={{
                padding: "8px 12px",
                borderRight: "1px solid #232428",
                borderBottom: "1px solid #232428",
                color: "#DEDEDE",
              }}
            >
              {children}
            </td>
          ),
          // Links
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#4A9EFF", textDecoration: "underline" }}
            >
              {children}
            </a>
          ),
          // Bold + strikethrough
          strong: ({ children }) => (
            <strong style={{ color: "#FFFFFF", fontWeight: 700 }}>{children}</strong>
          ),
          del: ({ children }) => (
            <del style={{ color: "#6A6A6A", textDecoration: "line-through" }}>{children}</del>
          ),
          // HR
          hr: () => (
            <hr style={{ border: "none", borderTop: "1px solid #232428", margin: "16px 0" }} />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default Markdown;
