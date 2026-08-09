/**
 * OpenForge — /new Landing Route (v4.1.0)
 * ========================================
 *
 * Visually identical to the root ``/`` route's empty state ("What can I
 * build for you?" + Forge logo behind) but always presents a FRESH session:
 * hitting ``/new`` immediately clears the ``sessionId`` so the next message
 * starts a brand-new chat rather than appending to the previous one.
 *
 * Implementation: reuses the same component as ``/`` via a small re-export
 * so the styles never drift between the two routes.
 *
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 * SPDX-License-Identifier: MIT
 */

"use client";

// Re-export the main page. Works because Page() derives "is this a brand
// new session?" from ``sessionId === null`` inside its own hook — hitting
// /new simply forces the empty-state landing screen.
import { useEffect } from "react";
import MainPage from "../page";

export default function NewSessionPage() {
  useEffect(() => {
    // Clear any lingering session id so the landing state shows.
    try {
      sessionStorage.removeItem("forge-session-id");
    } catch {
      /* ignore */
    }
  }, []);
  return <MainPage />;
}
