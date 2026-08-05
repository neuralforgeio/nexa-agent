/**
 * Unit tests — F-14 Onboarding (components/Onboarding.tsx)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Onboarding,
  LS_ONBOARDING,
  SAMPLE_PROMPT,
} from "@/components/Onboarding";

describe("Onboarding — step order & navigation", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("does not render when closed", () => {
    const { container } = render(<Onboarding open={false} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders step 1 (Welcome) when opened", () => {
    render(<Onboarding open onClose={() => {}} />);
    expect(screen.getByTestId("onboarding-step-welcome")).toBeInTheDocument();
  });

  it("steps advance in order: welcome → provider → sample → complete", async () => {
    render(<Onboarding open onClose={() => {}} />);
    // Step 1
    expect(screen.getByTestId("onboarding-step-welcome")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("onboarding-next"));
    // Step 2
    expect(screen.getByTestId("onboarding-step-provider")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("onboarding-next"));
    // Step 3
    expect(screen.getByTestId("onboarding-step-sample")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("onboarding-next"));
    // Step 4
    expect(screen.getByTestId("onboarding-step-complete")).toBeInTheDocument();
  });

  it("Back button takes the user one step back", async () => {
    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    expect(screen.getByTestId("onboarding-step-provider")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("onboarding-back"));
    expect(screen.getByTestId("onboarding-step-welcome")).toBeInTheDocument();
  });

  it("skip (Skip for now) marks LS flag and invokes onClose", async () => {
    const onClose = vi.fn();
    render(<Onboarding open onClose={onClose} />);
    await userEvent.click(screen.getByTestId("onboarding-skip"));
    expect(window.localStorage.getItem(LS_ONBOARDING)).toBe("1");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("close (X) button dismisses without marking complete", async () => {
    const onClose = vi.fn();
    render(<Onboarding open onClose={onClose} />);
    await userEvent.click(screen.getByLabelText(/close onboarding/i));
    expect(window.localStorage.getItem(LS_ONBOARDING)).toBeNull();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Finish on last step marks flag and closes", async () => {
    const onClose = vi.fn();
    render(<Onboarding open onClose={onClose} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-finish"));
    expect(window.localStorage.getItem(LS_ONBOARDING)).toBe("1");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Onboarding — provider form", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("provider select lists all four presets", async () => {
    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    expect(screen.getByRole("option", { name: /openai/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /ollama/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /tokenrouter/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /llama\.cpp/i })).toBeInTheDocument();
  });

  it("changing provider updates the model placeholder value", async () => {
    render(<Onboarding open onClose={() => {}} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    const model = screen.getByLabelText(/^model$/i) as HTMLInputElement;
    expect(model.value).toBe("gpt-4o-mini");
    await userEvent.selectOptions(screen.getByLabelText(/provider/i), "ollama");
    expect(model.value).toBe("llama3.1");
  });
});

describe("Onboarding — sample prompt", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("Run sample prompt invokes the callback with SAMPLE_PROMPT", async () => {
    const onRunSample = vi.fn();
    render(<Onboarding open onClose={() => {}} onRunSample={onRunSample} />);
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-next"));
    await userEvent.click(screen.getByTestId("onboarding-run-sample"));
    expect(onRunSample).toHaveBeenCalledTimes(1);
    expect(onRunSample).toHaveBeenCalledWith(SAMPLE_PROMPT);
  });
});

describe("Onboarding — first-run auto-open", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("opens by itself on first run (no localStorage flag)", async () => {
    render(<Onboarding />);
    // useEffect runs synchronously in tests after render.
    expect(await screen.findByTestId("onboarding-step-welcome")).toBeInTheDocument();
  });

  it("does NOT auto-open when completion flag already set", () => {
    window.localStorage.setItem(LS_ONBOARDING, "1");
    const { container } = render(<Onboarding />);
    expect(container.firstChild).toBeNull();
  });

  it("reopens from a completed state when forced open (resumable from settings)", async () => {
    window.localStorage.setItem(LS_ONBOARDING, "1");
    render(<Onboarding open onClose={() => {}} />);
    expect(screen.getByTestId("onboarding-step-welcome")).toBeInTheDocument();
  });
});
