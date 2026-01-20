import type { SessionStatus } from '@/types/api';

interface StatusBadgeProps {
  status: SessionStatus;
}

const statusConfig: Record<SessionStatus, { label: string; className: string }> = {
  pending: { label: 'Pending Payment', className: 'badge-pending' },
  active: { label: 'Ready to Play', className: 'badge-active' },
  playing: { label: 'Playing', className: 'badge-playing' },
  ended: { label: 'Ended', className: 'badge-ended' },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span className={config.className}>
      {config.label}
    </span>
  );
}
