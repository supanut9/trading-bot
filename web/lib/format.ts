export function formatDecimal(
  value: number | string | null | undefined,
  options?: Intl.NumberFormatOptions,
): string {
  if (value === null || value === undefined) {
    return "-";
  }

  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return "-";
  }

  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
    ...options,
  }).format(numericValue);
}

export function formatSignedDecimal(value: number | string | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }

  const numericValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numericValue)) {
    return "-";
  }

  const prefix = numericValue > 0 ? "+" : "";
  return `${prefix}${formatDecimal(numericValue, { maximumFractionDigits: 2 })}`;
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}
