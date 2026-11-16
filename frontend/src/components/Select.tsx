import * as RadixSelect from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

export interface SelectOption {
  value: string;
  label: string;
  /** language of the label, when it differs from the interface language */
  lang?: string;
}

interface Props {
  /** accessible name of the control */
  label: string;
  /** must be one of the option values (Radix does not allow an empty value) */
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  icon?: ReactNode;
  /** "pill": compact, inside the composer; "field": a form field */
  variant?: "pill" | "field";
  /** the value is not the default one: draw attention to it */
  highlighted?: boolean;
  align?: "start" | "end";
}

/** A select built on Radix: a button that opens a listbox, with arrow keys, Home / End,
 * type-ahead, Escape and focus return handled by the library. */
export function Select(props: Props) {
  const { label, value, options, onChange, icon, variant = "field", highlighted = false,
          align = "start" } = props;
  const selected = options.find((o) => o.value === value);
  const cls = ["select", `select--${variant}`, highlighted ? "is-set" : ""].filter(Boolean).join(" ");
  return (
    <RadixSelect.Root value={value} onValueChange={onChange}>
      <RadixSelect.Trigger className={cls} aria-label={label}>
        {icon}
        <span className="select__value" lang={selected?.lang}>
          <RadixSelect.Value>{selected?.label ?? ""}</RadixSelect.Value>
        </span>
        <RadixSelect.Icon className="select__chevron">
          <ChevronDown size={15} aria-hidden="true" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content className="select__content" position="popper" sideOffset={6}
                             align={align} collisionPadding={12}>
          <RadixSelect.Viewport className="select__viewport">
            {options.map((o) => (
              <RadixSelect.Item key={o.value} value={o.value} className="select__item">
                <RadixSelect.ItemText><span lang={o.lang}>{o.label}</span></RadixSelect.ItemText>
                <RadixSelect.ItemIndicator className="select__check">
                  <Check size={15} aria-hidden="true" />
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
