import { Link } from 'react-router-dom';
export default function PublicPlaceholder({ title, description, action='/choose' }: { title: string; description: string; action?: string }) {
  return <main className="ds-public"><nav><Link to="/" className="ds-brand"><span className="ds-logo">D</span><span>DataShield</span></Link><Link to="/login" className="ds-text-link">Log in</Link></nav><section><span className="ds-eyebrow">Continuous compliance</span><h1>{title}</h1><p>{description}</p><Link className="ds-button primary" to={action}>Get started <span>→</span></Link></section></main>;
}
