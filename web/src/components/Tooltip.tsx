interface TooltipProps {
  content: string;
  children: React.ReactNode;
}

export function Tooltip({ content, children }: TooltipProps) {
  return (
    <span className="relative group inline-block">
      {children}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1
                       text-xs text-white bg-gray-900 rounded whitespace-nowrap
                       opacity-0 group-hover:opacity-100 transition-opacity
                       pointer-events-none z-10">
        {content}
      </span>
    </span>
  );
}
