"use client";

// S-10: Plugin marketplace (browse / install / toggle community plugins).
interface PluginEntry {
  name: string; version: string; description: string; author: string; stars: number;
}

const MOCK: PluginEntry[] = [
  { name: "browser-use", version: "0.1.0", description: "Browser automation via Playwright", author: "community", stars: 120 },
  { name: "docx-report", version: "0.2.1", description: "Generate reports as .docx", author: "community", stars: 54 },
  { name: "voice-io", version: "0.3.0", description: "Voice input/output for Forge", author: "community", stars: 89 },
];

export function PluginMarketplace() {
  return (
    <div>
      {MOCK.map((p) => (
        <div key={p.name} style={{ padding: 12, borderBottom: "1px solid #24262B" }}>
          <div style={{ fontWeight: 600, color: "#ECECEC" }}>
            {p.name} <span style={{ color: "#6A6A6A" }}>v{p.version}</span>
          </div>
          <div style={{ fontSize: 13, color: "#9A9A9A" }}>{p.description}</div>
          <div style={{ fontSize: 12, color: "#6A6A6A" }}>by {p.author} · ★ {p.stars}</div>
        </div>
      ))}
    </div>
  );
}

export default PluginMarketplace;
