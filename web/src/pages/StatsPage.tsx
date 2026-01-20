import { useStats } from '@/hooks/useStats';
import { PotDisplay } from '@/components/PotDisplay';
import { LoadingScreen } from '@/components/LoadingSpinner';
import type { GameResult } from '@/types/api';

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDeathReason(reason: string | null): string {
  if (!reason) return 'Unknown';
  // Truncate long death reasons
  if (reason.length > 40) {
    return reason.slice(0, 37) + '...';
  }
  return reason;
}

function GameRow({ game, showPayout = false }: { game: GameResult; showPayout?: boolean }) {
  return (
    <tr>
      <td className="text-btc-orange">{game.username}</td>
      <td className="text-btc-gold tabular-nums">{game.score.toLocaleString()}</td>
      <td className="text-gray-400 text-xs hidden sm:table-cell">
        {game.ascended ? (
          <span className="text-pixel-green">Ascended!</span>
        ) : (
          formatDeathReason(game.death_reason)
        )}
      </td>
      <td className="text-gray-500 text-xs tabular-nums hidden md:table-cell">
        {game.turns.toLocaleString()}
      </td>
      {showPayout && (
        <td className="text-pixel-green tabular-nums">
          {game.payout_sats ? `${game.payout_sats.toLocaleString()} sats` : '-'}
        </td>
      )}
      <td className="text-gray-600 text-xs">{formatDate(game.ended_at)}</td>
    </tr>
  );
}

export function StatsPage() {
  const { stats, loading, error, refetch } = useStats({ pollInterval: 30000 });

  if (loading) {
    return <LoadingScreen message="Loading stats..." />;
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 text-center">
        <p className="text-pixel-red mb-4">{error}</p>
        <button onClick={refetch} className="btn-secondary text-xs">
          Retry
        </button>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="font-pixel text-btc-orange text-lg mb-4">Leaderboard</h1>
        <PotDisplay size="md" showAnte={false} />
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div className="card text-center">
          <p className="text-gray-500 text-xs mb-1">Total Games</p>
          <p className="font-pixel text-btc-gold text-lg">{stats.total_games}</p>
        </div>
        <div className="card text-center">
          <p className="text-gray-500 text-xs mb-1">Ascensions</p>
          <p className="font-pixel text-pixel-green text-lg">{stats.total_ascensions}</p>
        </div>
        <div className="card text-center">
          <p className="text-gray-500 text-xs mb-1">High Score</p>
          <p className="font-pixel text-btc-orange text-lg">
            {stats.high_score?.toLocaleString() ?? '-'}
          </p>
        </div>
        <div className="card text-center">
          <p className="text-gray-500 text-xs mb-1">Avg Score</p>
          <p className="font-pixel text-gray-400 text-lg">
            {stats.avg_score ? Math.round(stats.avg_score).toLocaleString() : '-'}
          </p>
        </div>
      </div>

      {/* Hall of Fame (Ascensions) */}
      {stats.ascensions.length > 0 && (
        <section className="mb-8">
          <h2 className="font-pixel text-pixel-green text-sm mb-4 flex items-center gap-2">
            <span>🏆</span> Hall of Fame
          </h2>
          <div className="card-glow border-pixel-green/30 overflow-x-auto">
            <table className="table-pixel">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Score</th>
                  <th className="hidden sm:table-cell">Result</th>
                  <th className="hidden md:table-cell">Turns</th>
                  <th>Payout</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {stats.ascensions.map((game) => (
                  <GameRow key={game.id} game={game} showPayout />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* High Scores */}
      <section className="mb-8">
        <h2 className="font-pixel text-btc-gold text-sm mb-4 flex items-center gap-2">
          <span>⭐</span> High Scores
        </h2>
        <div className="card overflow-x-auto">
          {stats.leaderboard.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No games played yet</p>
          ) : (
            <table className="table-pixel">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Score</th>
                  <th className="hidden sm:table-cell">Death</th>
                  <th className="hidden md:table-cell">Turns</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {stats.leaderboard.map((game) => (
                  <GameRow key={game.id} game={game} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Recent Games */}
      <section>
        <h2 className="font-pixel text-btc-orange text-sm mb-4 flex items-center gap-2">
          <span>📜</span> Recent Games
        </h2>
        <div className="card overflow-x-auto">
          {stats.recent_games.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No games played yet</p>
          ) : (
            <table className="table-pixel">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Score</th>
                  <th className="hidden sm:table-cell">Death</th>
                  <th className="hidden md:table-cell">Turns</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_games.map((game) => (
                  <GameRow key={game.id} game={game} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Auto-refresh notice */}
      <p className="text-center text-gray-600 text-xs mt-8">
        Stats auto-refresh every 30 seconds
      </p>
    </div>
  );
}
