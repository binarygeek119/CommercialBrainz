export const LOGO_METADATA_FIELDS = [
  { key: "label", label: "Version label" },
  { key: "year", label: "Year" },
  { key: "month", label: "Month" },
  { key: "event", label: "Event / occasion" },
  { key: "notes", label: "Notes" },
] as const;

export function logoFieldLabel(key: string): string {
  const found = LOGO_METADATA_FIELDS.find((f) => f.key === key);
  return found?.label ?? key.replace(/_/g, " ");
}

export function formatLogoFieldValue(key: string, value: unknown): string {
  if (value == null || value === "") return "—";
  if (key === "month" && typeof value === "number") {
    const months = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];
    return months[value - 1] ?? String(value);
  }
  return String(value);
}
