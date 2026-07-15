"use client";

import { useEffect, useState } from "react";
import { NEXA_BANNER, NEXA_BOOT_SEQUENCE } from "@/lib/nexa/constants";

/**
 * Terminal boot overlay. Types out the Nexa banner and boot diagnostics,
 * then calls onDone. Click anywhere to skip.
 */
export function BootSequence({ onDone }: { onDone: () => void }) {
  const lines = [NEXA_BANNER, ...NEXA_BOOT_SEQUENCE, "[nexa] launching interface ..."];
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (shown >= lines.length) {
      const t = setTimeout(onDone, 450);
      return () => clearTimeout(t);
    }
    const delay = shown === 0 ? 120 : 220;
    const t = setTimeout(() => setShown((s) => s + 1), delay);
    return () => clearTimeout(t);
  }, [shown]);

  return (
    <div
      onClick={onDone}
      className="fixed inset-0 z-50 flex items-center justify-center bg-background nexa-scanlines cursor-pointer"
    >
      <div className="w-full max-w-2xl px-6 sm:px-10">
        <pre className="text-emerald-400 nexa-glow text-[10px] sm:text-xs leading-tight whitespace-pre">
          {lines.slice(0, shown).join("\n")}
          {shown < lines.length && (
            <span className="nexa-cursor inline-block" />
          )}
        </pre>
        <p className="mt-6 text-xs text-muted-foreground">
          click to skip &rarr;
        </p>
      </div>
    </div>
  );
}
