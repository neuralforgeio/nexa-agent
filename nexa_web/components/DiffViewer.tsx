"use client";

// H-03: Unified diff viewer with line-level highlighting.
import React from "react";

export function DiffViewer({ diff, maxHeight = 300 }: { diff: string; maxHeight?: number }) {
  const lines = diff.split("\n");
  return (
    <pre style={{
      background: "#0B0C0E", border: "1px solid #24262B", borderRadius: 8,
      padding: 12, overflow: "auto", maxHeight, fontSize: 12, fontFamily: "monospace", color: "#ECECEC",
    }}>
      {lines.map((l, i) => {
        const isAdd = l.startsWith("+");
        const isDel = l.startsWith("-");
        return (
          <div
            key={i}
            style={{
              color: isAdd ? "#4ADE80" : isDel ? "#F87171" : "#9A9A9A",
              background: isAdd ? "rgba(74,222,128,0.06)" : isDel ? "rgba(248,113,113,0.06)" : "transparent",
            }}
          >
            {l || " "}
          </div>
        );
      })}
    </pre>
  );
}

export default DiffViewer;
