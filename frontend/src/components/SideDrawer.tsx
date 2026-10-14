import { X } from 'lucide-react';
import type { ReactNode } from 'react';

export function SideDrawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside className="side-drawer" role="dialog" aria-modal="true" aria-label={title}>
        <header><div><span className="drawer-kicker">DETAILS</span><h2>{title}</h2></div><button className="icon-button" aria-label="Close details" onClick={onClose}><X size={18} /></button></header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
