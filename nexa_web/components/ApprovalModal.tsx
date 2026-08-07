"use client";
import { useEffect, useRef, useState } from "react";
import { DiffViewer } from "./DiffViewer";

export interface ApprovalRequest {
  id: string; tool: string; command?: string; diff?: string; reason: string;
}
export function ApprovalModal({ request, onApprove, onDeny, onAlwaysAllow }: {
  request: ApprovalRequest; onApprove: () => void; onDeny: () => void; onAlwaysAllow: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onDeny(); };
    document.addEventListener("keydown", h, true);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", h, true); document.body.style.overflow = ""; };
  }, [onDeny]);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}
      onClick={onDeny}>
      <div ref={ref} role="dialog" aria-modal="true" onClick={(e)=>e.stopPropagation()}
        style={{ width: 560, maxHeight: "80vh", overflowY: "auto", background: "#141618", border: "1px solid #2E2F34", borderRadius: 12, padding: 20, color: "#ECECEC" }}>
        <h3 style={{ marginTop: 0 }}>Approval Required: {request.tool}</h3>
        <p style={{ color: "#9A9A9A" }}>{request.reason}</p>
        {request.diff && <div style={{ margin: "12px 0" }}><DiffViewer diff={request.diff} /></div>}
        {request.command && <pre style={{ background: "#0B0C0E", padding: 10, borderRadius: 6 }}>{request.command}</pre>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 16 }}>
          <button onClick={onDeny} style={{ background: "transparent", border: "1px solid #F87171", color: "#F87171", padding: "8px 14px", borderRadius: 6 }}>Deny (Esc)</button>
          <button onClick={onAlwaysAllow} style={{ background: "transparent", border: "1px solid #FBBF24", color: "#FBBF24", padding: "8px 14px", borderRadius: 6 }}>Always Allow</button>
          <button onClick={onApprove} style={{ background: "#4A9EFF", border: "none", color: "#fff", padding: "8px 14px", borderRadius: 6 }}>Approve</button>
        </div>
      </div>
    </div>
  );
}
