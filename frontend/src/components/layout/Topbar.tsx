import React from 'react';
import { Moon, Sun, ShieldCheck, Menu } from 'lucide-react';

interface TopbarProps {
  onMenuClick: () => void;
}

const Topbar: React.FC<TopbarProps> = ({ onMenuClick }) => {
  // Hardcoded dark mode for Milestone 1 as requested (dark mode first).
  const isDark = true;

  return (
    <div className="h-16 border-b border-border bg-surface/50 backdrop-blur-sm flex items-center justify-between px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button 
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-2 text-textSecondary hover:text-textPrimary hover:bg-surfaceHover rounded-md transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <h2 className="text-sm font-semibold text-textPrimary hidden sm:block">Project / FedRouteAI v1.0</h2>
        <h2 className="text-sm font-semibold text-textPrimary sm:hidden">FedRouteAI v1.0</h2>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 bg-success/10 text-success px-3 py-1.5 rounded-full text-xs font-medium border border-success/20">
          <ShieldCheck className="w-3.5 h-3.5" />
          Model Status: Stable
        </div>
        
        <button className="p-2 text-textSecondary hover:text-textPrimary hover:bg-surfaceHover rounded-md transition-colors">
          {isDark ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};

export default Topbar;
