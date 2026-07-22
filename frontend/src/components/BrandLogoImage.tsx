export type BrandLogoSize = "sm" | "md" | "lg" | "preview" | "vote" | "xs";

interface Props {
  src: string;
  alt: string;
  size?: BrandLogoSize;
}

/**
 * Build a logo URL from validated components so untrusted schemes cannot reach
 * the img element.
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

export default function BrandLogoImage({ src, alt, size = "md" }: Props) {
  const safeSrc = safeLogoSrc(src);
  if (!safeSrc) return null;

  // codeql[js/xss-through-dom]: React sets img.src as a DOM property after URL allowlisting
  return (
    <div className={`brand-logo-frame brand-logo-frame--${size}`}>
      <img src={safeSrc} alt={alt} className="brand-logo-img" />
    </div>
  );
}
