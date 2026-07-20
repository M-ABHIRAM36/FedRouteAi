import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Map, Settings2, Network, BarChart3, FileText, Database, Info } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Traffic Map', path: '/map', icon: Map },
  { name: 'Prediction', path: '/prediction', icon: Settings2 },
  { name: 'Federated', path: '/federated', icon: Network },
  { name: 'Training', path: '/training', icon: BarChart3 },
  { name: 'Analysis', path: '/analysis', icon: FileText },
  { name: 'Results', path: '/results', icon: Database },
  { name: 'About', path: '/about', icon: Info },
];

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, setIsOpen }) => {
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden" 
          onClick={() => setIsOpen(false)}
        />
      )}
      <div className={twMerge(clsx(
        'fixed md:static inset-y-0 left-0 z-50 w-64 bg-surface border-r border-border h-full flex flex-col transition-transform duration-200 ease-in-out',
        isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      ))}>
        <div className="h-16 flex items-center px-6 border-b border-border">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-primary inline-block"></span>
            FedRouteAI
          </h1>
        </div>
        <nav className="flex-1 py-4 flex flex-col gap-1 px-3 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                twMerge(
                  clsx(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-textSecondary hover:bg-surfaceHover hover:text-textPrimary'
                  )
                )
              }
              onClick={() => setIsOpen(false)}
              aria-label={`Navigate to ${item.name}`}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border">
          <div className="text-xs text-textSecondary text-center">
            v1.0 Stable Release
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
