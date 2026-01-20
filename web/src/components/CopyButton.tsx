import { useCopyToClipboard } from '@/hooks/useCopyToClipboard';

interface CopyButtonProps {
  text: string;
  label?: string;
  className?: string;
}

export function CopyButton({ text, label = 'Copy', className = '' }: CopyButtonProps) {
  const { copied, copy } = useCopyToClipboard();

  return (
    <button
      onClick={() => copy(text)}
      className={`px-3 py-1 text-xs font-mono rounded border transition-all duration-200 ${
        copied
          ? 'bg-pixel-green/20 border-pixel-green text-pixel-green'
          : 'bg-dark-surface border-dark-border text-gray-400 hover:border-btc-orange hover:text-btc-orange'
      } ${className}`}
    >
      {copied ? 'Copied!' : label}
    </button>
  );
}
