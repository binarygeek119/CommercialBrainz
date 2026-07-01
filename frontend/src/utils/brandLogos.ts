export const LOGO_MONTHS = [
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

export function formatLogoContext(state: Record<string, unknown>): string {
  const parts: string[] = [];
  if (typeof state.label === "string" && state.label.trim()) parts.push(state.label.trim());
  if (typeof state.year === "number") {
    let date = String(state.year);
    if (typeof state.month === "number") date = `${state.year}-${String(state.month).padStart(2, "0")}`;
    parts.push(date);
  }
  if (typeof state.event === "string" && state.event.trim()) parts.push(state.event.trim());
  return parts.length ? parts.join(" · ") : "Logo version";
}
