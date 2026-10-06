export default function RoutePlaceholder({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="ds-page"><header className="ds-page-header"><span className="ds-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></header><section className="ds-empty"><div className="ds-empty-mark">D</div><h2>This workspace is being prepared.</h2><p>The experience will connect to your existing DataShield evidence and analysis.</p></section></div>;
}
