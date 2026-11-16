import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** Open the select with this accessible name and pick an option by its text. */
export async function choose(label: string, option: string) {
  await userEvent.click(screen.getByRole("combobox", { name: label }));
  await userEvent.click(await screen.findByRole("option", { name: option }));
}

/** The text of the selected option, as shown in the closed select. */
export function selected(label: string): string {
  return screen.getByRole("combobox", { name: label }).textContent ?? "";
}
