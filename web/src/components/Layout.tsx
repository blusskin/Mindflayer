import { Link, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const navLinks = [
    { to: '/', label: 'Home' },
    { to: '/play', label: 'Play' },
    { to: '/stats', label: 'Leaderboard' },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-dark-border bg-dark-surface/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <span className="text-2xl">🍊</span>
            <span className="font-pixel text-btc-orange text-xs sm:text-sm group-hover:text-btc-gold transition-colors">
              Orange Nethack
            </span>
            <span className="text-xl">⚡</span>
          </Link>

          <nav className="flex items-center gap-2 sm:gap-4">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`font-pixel text-[10px] sm:text-xs px-2 sm:px-3 py-2 rounded transition-all duration-200 ${
                  location.pathname === link.to
                    ? 'text-btc-orange bg-btc-orange/10'
                    : 'text-gray-400 hover:text-btc-orange hover:bg-dark-surface'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-dark-border py-8 mt-auto">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <p className="text-gray-500 text-sm">
            Stack sats. Ascend. Win the pot.
          </p>
          <p className="text-gray-600 text-xs mt-2">
            Powered by Bitcoin Lightning ⚡
          </p>
        </div>
      </footer>
    </div>
  );
}
