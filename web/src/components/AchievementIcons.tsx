import { Tooltip } from './Tooltip';

interface Achievement {
  bit: number;
  name: string;
  emoji: string;
}

const ACHIEVEMENTS: Achievement[] = [
  { bit: 0x0001, name: 'Bell of Opening', emoji: '🔔' },
  { bit: 0x0002, name: 'Candelabrum', emoji: '🕯️' },
  { bit: 0x0004, name: 'Book of the Dead', emoji: '📖' },
  { bit: 0x0008, name: 'Invocation', emoji: '🌀' },
  { bit: 0x0010, name: 'Amulet', emoji: '📿' },
  { bit: 0x0020, name: 'Elemental Planes', emoji: '✨' },
  { bit: 0x0040, name: 'Astral Plane', emoji: '💫' },
  { bit: 0x0080, name: 'Ascended', emoji: '🏆' },
  { bit: 0x0100, name: 'Quest Complete', emoji: '🎯' },
  { bit: 0x0200, name: 'Gehennom', emoji: '🔥' },
  { bit: 0x0400, name: 'Mines End', emoji: '⛏️' },
  { bit: 0x0800, name: 'Sokoban', emoji: '📦' },
];

function parseAchieveHex(achieve: string): number {
  if (!achieve) return 0;
  const cleaned = achieve.replace(/^0x/i, '');
  return parseInt(cleaned, 16) || 0;
}

interface AchievementIconsProps {
  achieve: string | null;
}

export function AchievementIcons({ achieve }: AchievementIconsProps) {
  if (!achieve) return null;

  const achieveBits = parseAchieveHex(achieve);
  if (achieveBits === 0) return null;

  const earnedAchievements = ACHIEVEMENTS.filter(a => achieveBits & a.bit);
  if (earnedAchievements.length === 0) return null;

  return (
    <span className="inline-flex gap-0.5">
      {earnedAchievements.map(a => (
        <Tooltip key={a.bit} content={a.name}>
          <span className="cursor-help text-xs">{a.emoji}</span>
        </Tooltip>
      ))}
    </span>
  );
}
