/**
 * Nexa Agent — Core Constants
 *
 * Central registry of brand identity, version, and runtime paths for Nexa Agent.
 * Authored by Dearly Febriano Irwansyah.
 *
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2026 Dearly Febriano Irwansyah
 */

export const NEXA_NAME = "Nexa Agent";
export const NEXA_SHORT = "Nexa";
export const NEXA_VERSION = "1.0.0";
export const NEXA_AUTHOR = "Dearly Febriano Irwansyah";
export const NEXA_LICENSE = "MIT";
export const NEXA_TAGLINE = "The advanced AI agent by Dearly Febriano Irwansyah";

/**
 * Logical "home directory" for Nexa runtime artifacts.
 * In this web build, NEXA_HOME is a logical namespace backed by the database
 * rather than a filesystem path (~/.nexa/ in the CLI build). We keep the name
 * to preserve architectural parity with the reference design.
 */
export const NEXA_HOME = "~/.nexa";

/**
 * Named profile under NEXA_HOME. A profile scopes sessions, memory and skills.
 * The "default" profile is created on first run.
 */
export const NEXA_PROFILE = "default";

/**
 * Subdirectories managed under NEXA_HOME.
 */
export const NEXA_DIRS = {
  sessions: `${NEXA_HOME}/sessions`,
  skills: `${NEXA_HOME}/skills`,
  memory: `${NEXA_HOME}/memory`,
  logs: `${NEXA_HOME}/logs`,
} as const;

/**
 * Memory file names living inside NEXA_DIRS.memory.
 */
export const NEXA_MEMORY_FILES = {
  memory: "MEMORY.md",
  user: "USER.md",
} as const;

/**
 * Conversation loop safeguards.
 */
export const NEXA_MAX_TOOL_ITERATIONS = 8;
export const NEXA_MAX_CONTEXT_MESSAGES = 30;

/**
 * Default model identifier resolved by the provider.
 */
export const NEXA_DEFAULT_MODEL = "nexa-core";

/**
 * Filesystem sandbox root for file & terminal tools. All file operations
 * are confined here to prevent arbitrary host access.
 */
export const NEXA_WORKSPACE = `${process.cwd()}/nexa-workspace`;

/**
 * Boot banner shown in the terminal UI on startup.
 */
export const NEXA_BANNER = [
  " _   _           _    ",
  "| \\ | | _____  _| |_  ",
  "|  \\| |/ _ \\ \\/ / __| ",
  "| |\\  |  __/>  <| |_  ",
  "|_| \\_|\\___/_/\\_\\\\__| ",
  `  Agent v${NEXA_VERSION} — ${NEXA_TAGLINE}`,
].join("\n");

/**
 * Boot-time diagnostics lines (parody of a CLI boot sequence).
 */
export const NEXA_BOOT_SEQUENCE: readonly string[] = [
  `[nexa] initializing runtime @ ${NEXA_HOME}`,
  `[nexa] profile: ${NEXA_PROFILE}`,
  `[nexa] loading tool registry ...`,
  `[nexa] mounting provider 'nexa-core' ...`,
  `[nexa] restoring memory store ...`,
  `[nexa] agent ready.`,
];
