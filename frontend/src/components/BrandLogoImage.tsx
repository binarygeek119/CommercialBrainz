export type BrandLogoSize = "sm" | "md" | "lg" | "preview" | "vote" | "xs";

interface Props {
  src: string;
  alt: string;
  size?: BrandLogoSize;
}

/** Allow only http(s), site-relative, or blob URLs for logo images. */
function safeLogoSrc(src: string): string | null {
  const value = src.trim();
  if (!value) return null;
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  if (value.startsWith("blob:")) return value;
  try {
    const parsed = new URL(value);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

export default function BrandLogoImage({ src, alt, size = "md" }: Props) {
  const safeSrc = safeLogoSrc(src);
  if (!safeSrc) return null;

  return (
    <div className={`brand-logo-frame brand-logo-frame--${size}`}>
      <img src={safeSrc} alt={alt} className="brand-logo-img" />
    </div>
  );
}
