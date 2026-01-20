import { usePot } from '@/hooks/usePot';

interface PotDisplayProps {
  size?: 'sm' | 'md' | 'lg';
  showAnte?: boolean;
  className?: string;
}

export function PotDisplay({ size = 'md', showAnte = true, className = '' }: PotDisplayProps) {
  const { pot, loading, error } = usePot();

  const sizeClasses = {
    sm: 'text-lg sm:text-xl',
    md: 'text-2xl sm:text-4xl',
    lg: 'text-4xl sm:text-6xl',
  };

  const labelClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base sm:text-lg',
  };

  if (error) {
    return (
      <div className={`text-center ${className}`}>
        <p className="text-pixel-red text-sm">Failed to load pot</p>
      </div>
    );
  }

  return (
    <div className={`text-center ${className}`}>
      <p className={`text-gray-400 ${labelClasses[size]} mb-1`}>Current Pot</p>
      <p className={`font-pixel text-btc-gold ${sizeClasses[size]} tracking-wider`}>
        {loading ? (
          <span className="animate-pulse">Loading...</span>
        ) : (
          <>
            {pot?.balance_sats.toLocaleString()}
            <span className="text-btc-orange ml-2">sats</span>
          </>
        )}
      </p>
      {showAnte && pot && (
        <p className={`text-gray-500 ${labelClasses[size]} mt-2`}>
          Ante: <span className="text-btc-orange">{pot.ante_sats.toLocaleString()} sats</span>
        </p>
      )}
    </div>
  );
}
