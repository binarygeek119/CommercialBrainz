export type BrandLogoSize = "sm" | "md" | "lg" | "preview" | "vote" | "xs";

interface Props {
  src: string;
  alt: string;
  size?: BrandLogoSize;
}

export default function BrandLogoImage({ src, alt, size = "md" }: Props) {
  return (
    <div className={`brand-logo-frame brand-logo-frame--${size}`}>
      <img src={src} alt={alt} className="brand-logo-img" />
    </div>
  );
}
