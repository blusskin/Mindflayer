import { Tooltip } from './Tooltip';

interface Conduct {
  bit: number;
  name: string;
  emoji: string;
}

const CONDUCTS: Conduct[] = [
  { bit: 0x001, name: 'Foodless', emoji: '🍽️' },
  { bit: 0x002, name: 'Vegan', emoji: '🌱' },
  { bit: 0x004, name: 'Vegetarian', emoji: '🥕' },
  { bit: 0x008, name: 'Atheist', emoji: '🚫' },
  { bit: 0x010, name: 'Weaponless', emoji: '👊' },
  { bit: 0x020, name: 'Pacifist', emoji: '☮️' },
  { bit: 0x040, name: 'Illiterate', emoji: '📕' },
  { bit: 0x080, name: 'Polypileless', emoji: '💊' },
  { bit: 0x100, name: 'Polyselfless', emoji: '🦎' },
  { bit: 0x200, name: 'Wishless', emoji: '⭐' },
  { bit: 0x400, name: 'Artiwishless', emoji: '🗡️' },
  { bit: 0x800, name: 'Genocideless', emoji: '🕊️' },
];

function parseConductHex(conduct: string): number {
  if (!conduct) return 0;
  const cleaned = conduct.replace(/^0x/i, '');
  return parseInt(cleaned, 16) || 0;
}

interface ConductIconsProps {
  conduct: string | null;
}

export function ConductIcons({ conduct }: ConductIconsProps) {
  if (!conduct) return null;

  const conductBits = parseConductHex(conduct);
  if (conductBits === 0) return null;

  const achievedConducts = CONDUCTS.filter(c => conductBits & c.bit);
  if (achievedConducts.length === 0) return null;

  return (
    <span className="inline-flex gap-0.5">
      {achievedConducts.map(c => (
        <Tooltip key={c.bit} content={c.name}>
          <span className="cursor-help text-xs">{c.emoji}</span>
        </Tooltip>
      ))}
    </span>
  );
}
