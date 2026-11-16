import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Session } from "../state/history";
import { renderIn } from "../test/render";
import { PASSAGE_UZ, askResponse } from "../test/samples";
import { SearchHistory } from "./SearchHistory";

function session(id: string, title: string): Session {
  return {
    id, title, updatedAt: Date.UTC(2026, 10, 16),
    turns: [{ id: `${id}-1`, question: title, corpus: "real", documentId: null,
              response: askResponse(title, [PASSAGE_UZ]) }],
  };
}

const SESSIONS = [session("a", "Penya qachon hisoblanadi?"), session("b", "Когда вносится плата?")];

describe("SearchHistory", () => {
  it("says where the history is kept, also when it is empty", () => {
    renderIn(<SearchHistory sessions={[]} activeId={null} onOpen={() => {}} onDelete={() => {}}
                            onClear={() => {}} />, "ru");
    expect(screen.getByText("Здесь появятся ваши запросы.")).toBeTruthy();
    expect(screen.getByText("Хранится только в этом браузере.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("opens and deletes a session and marks the open one", async () => {
    const onOpen = vi.fn();
    const onDelete = vi.fn();
    renderIn(<SearchHistory sessions={SESSIONS} activeId="b" onOpen={onOpen} onDelete={onDelete}
                            onClear={() => {}} />);
    const open = screen.getByRole("button", { name: /^Когда вносится плата\?/ });
    expect(open.getAttribute("aria-current")).toBe("true");
    await userEvent.click(screen.getByRole("button", { name: /^Penya qachon hisoblanadi\?/ }));
    expect(onOpen).toHaveBeenCalledWith(SESSIONS[0]);
    await userEvent.click(screen.getByRole("button", { name: "Delete “Когда вносится плата?”" }));
    expect(onDelete).toHaveBeenCalledWith("b");
  });

  it("clears the history only after a second click", async () => {
    const onClear = vi.fn();
    renderIn(<SearchHistory sessions={SESSIONS} activeId={null} onOpen={() => {}} onDelete={() => {}}
                            onClear={onClear} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClear).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Delete all?" }));
    expect(onClear).toHaveBeenCalledOnce();
  });
});
