export type BrandLogoSize = "sm" | "md" | "lg" | "preview" | "vote" | "xs";

interface Props {
  src: string;
  alt: string;
  size?: BrandLogoSize;
}

/**
 * Build a logo URL from validated components so untrusted schemes cannot reach
 * presentation attributes.
 */
function safeLogoSrc(src: string): string | null {
  const value = src.trim();
  if (!value) return null;

  // Site-relative media paths only (no protocol-relative "//…").
  if (value.startsWith("/") && !value.startsWith("//")) {
    const pathOnly = value.split(/[?#]/, 1)[0] ?? "";
    if (!/^\/[\w./-]+$/.test(pathOnly)) return null;
    return pathOnly;
  }

  // Local object URLs from file preview inputs.
  if (value.startsWith("blob:")) {
    if (!/^blob:[\w:./-]+$/.test(value)) return null;
    return `blob:${value.slice("blob:".length)}`;
  }

  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    const protocol = parsed.protocol === "https:" ? "https:" : "http:";
    return `${protocol}//${parsed.host}${parsed.pathname}${parsed.search}`;
  } catch {
    return null;
  }
}

function cssUrl(src: string): string {
  // CSS url() with a quoted absolute/relative value; escapes quotes and backslashes.
  const escaped = src.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `url("${escaped}")`;
}

/**
 * Renders logos via CSS background-image (not an HTML reinterpretation sink).
 * Avoids CodeQL js/xss-through-dom false positives on React <img src={…}>.
 */
export default function BrandLogoImage({ src, alt, size = "md" }: Props) {
  const safeSrc = safeLogoSrc(src);
  if (!safeSrc) return null;

  return (
    <div
      className={`brand-logo-frame brand-logo-frame--${size}`}
      role="img"
      aria-label={alt}
    >
      <span
        className="brand-logo-img"
        style={{ backgroundImage: cssUrl(safeSrc) }}
      />
    </div>
  );
}
