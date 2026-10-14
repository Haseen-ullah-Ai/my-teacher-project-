import { createContext, useContext, useEffect, useState } from 'react';
import {
  Activity,
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  Command,
  Database,
  FileClock,
  Files,
  LayoutDashboard,
  Menu,
  Moon,
  Settings,
  Sun,
  Wrench,
  X,
} from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useHealth } from '../api/hooks';
import { ToastViewport } from './ui';

const navItems = [
  { label: 'Overview', to: '/', icon: LayoutDashboard },
  { label: 'Runs', to: '/runs', icon: FileClock },
  { label: 'Documents', to: '/documents', icon: Files },
  { label: 'Datasets', to: '/datasets', icon: Database },
  { label: 'Tools', to: '/tools', icon: Wrench },
];

const titles: Record<string, string> = {
  '/': 'Overview',
  '/runs': 'Runs',
  '/runs/new': 'New research',
  '/documents': 'Documents',
  '/datasets': 'Datasets',
  '/tools': 'Tools',
  '/settings': 'Settings',
};

export type ThemePreference = 'system' | 'light' | 'dark';
interface ThemeContextValue {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
}
const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function useThemePreference(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useThemePreference must be used inside AppShell');
  return context;
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [preference, setPreference] = useState<ThemePreference>(() => {
    const saved = localStorage.getItem('researchpilot-theme');
    return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system';
  });
  const [systemDark, setSystemDark] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches);
  const theme = preference === 'system' ? systemDark ? 'dark' : 'light' : preference;
  const location = useLocation();
  const health = useHealth();
  const routeTitle = location.pathname.startsWith('/runs/') && location.pathname !== '/runs/new'
    ? 'Run details'
    : titles[location.pathname] ?? 'ResearchPilot';

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('researchpilot-theme', preference);
  }, [preference, theme]);

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    media.addEventListener('change', handleChange);
    return () => media.removeEventListener('change', handleChange);
  }, []);

  return (
    <ThemeContext.Provider value={{ preference, setPreference }}>
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'sidebar-mobile-open' : ''}`} aria-label="Primary navigation">
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={20} /></div>
          {!collapsed && <div className="brand-name">Research<span>Pilot</span><small>CONTROLLED RESEARCH</small></div>}
          <button className="icon-button sidebar-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="workspace-switch"><div className="workspace-avatar">N</div>{!collapsed && <><div><strong>Northwind Group</strong><small>Research workspace</small></div><ChevronRight size={15} /></>}</div>
        <nav className="nav-list">
          <span className="nav-caption">{!collapsed && 'WORKSPACE'}</span>
          {navItems.map(({ label, to, icon: Icon }) => (
            <NavLink end={to === '/'} key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`} title={collapsed ? label : undefined}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
          <span className="nav-caption secondary-caption">{!collapsed && 'PREFERENCES'}</span>
          <NavLink to="/settings" onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`} title={collapsed ? 'Settings' : undefined}>
            <Settings size={18} /><span>Settings</span>
          </NavLink>
        </nav>
        {!collapsed && <div className="sidebar-footer"><BookOpenText size={16} /><div><strong>Local-first by design</strong><span>Research stays in your workspace.</span></div></div>}
        <button className="collapse-toggle" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {collapsed ? <ChevronRight size={17} /> : <><ChevronLeft size={17} /><span>Collapse</span></>}
        </button>
      </aside>
      {mobileOpen && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <div className="main-frame">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></button>
            <span className="breadcrumb-root"><Command size={15} /> Workspace</span><ChevronRight size={14} className="breadcrumb-chevron" /><span className="breadcrumb-current">{routeTitle}</span>
          </div>
          <div className="topbar-actions">
            <div className={`health-pill ${health.isError ? 'health-down' : health.data?.status === 'ok' ? 'health-up' : ''}`} title={health.error instanceof Error ? health.error.message : 'Backend connection status'}>
              <span className="health-dot" />{health.isLoading ? 'Connecting' : health.data?.status === 'ok' ? 'API connected' : 'API offline'}
            </div>
            <button className="icon-button theme-toggle" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} onClick={() => setPreference(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
            <div className="user-avatar" aria-label="Workspace profile">RP</div>
          </div>
        </header>
        <main className="page-content"><Outlet /></main>
      </div>
      <ToastViewport />
    </div>
    </ThemeContext.Provider>
  );
}
