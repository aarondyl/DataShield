export default function BrandLogo({ size = 30 }: { size?: number }) {
  const radius = Math.max(7, Math.round(size * 0.26));
  return (
    <span className="ds-brand-logo" style={{ width: size, height: size, borderRadius: radius }}>
      <img src="/logo.png" alt="DataShield" width={size} height={size} />
    </span>
  );
}
