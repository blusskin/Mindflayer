import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useSession } from '@/hooks/useSession';
import { StatusBadge } from '@/components/StatusBadge';
import { CopyButton } from '@/components/CopyButton';
import { LoadingScreen } from '@/components/LoadingSpinner';

export function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const id = sessionId ? parseInt(sessionId, 10) : null;
  const token = searchParams.get('token');

  const { session, loading, error, refetch } = useSession(id, token, {
    pollInterval: 5000,
    stopOnActive: false, // Keep polling to show status updates
  });

  if (!id || isNaN(id)) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <p className="text-pixel-red mb-4">Invalid session ID</p>
        <Link to="/play" className="btn-primary text-xs">
          Start New Game
        </Link>
      </div>
    );
  }

  if (loading) {
    return <LoadingScreen message="Loading session..." />;
  }

  if (error) {
    const isAccessDenied = error.includes('access token') || error.includes('403');
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 text-center">
        <h1 className="font-pixel text-btc-orange text-sm mb-4">
          {isAccessDenied ? 'Access Denied' : 'Session Not Found'}
        </h1>
        <p className="text-gray-400 mb-6">
          {isAccessDenied
            ? 'This session requires an access token. Please use the link from your payment confirmation email.'
            : error}
        </p>
        <div className="flex gap-4 justify-center">
          <button onClick={refetch} className="btn-secondary text-xs">
            Retry
          </button>
          <Link to="/play" className="btn-primary text-xs">
            Start New Game
          </Link>
        </div>
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="card-glow">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="font-pixel text-btc-orange text-sm mb-2">
            Session #{session.id}
          </h1>
          <StatusBadge status={session.status} />
        </div>

        {/* Session Details */}
        <div className="space-y-4">
          {/* Pending Payment */}
          {session.status === 'pending' && (
            <div className="bg-yellow-900/20 border border-yellow-500/30 rounded p-4 text-center">
              <p className="text-yellow-500 text-sm mb-2">Awaiting Payment</p>
              <p className="text-gray-400 text-xs">
                This session is waiting for the Lightning invoice to be paid.
                Return to the play page to see the QR code.
              </p>
              <Link to="/play" className="btn-primary text-xs mt-4 inline-block">
                Return to Play
              </Link>
            </div>
          )}

          {/* Active/Playing - Show Credentials */}
          {(session.status === 'active' || session.status === 'playing') && (
            <>
              <div className="bg-pixel-green/10 border border-pixel-green/30 rounded p-4 text-center">
                <p className="text-pixel-green text-sm mb-1">
                  {session.status === 'active' ? 'Ready to Play!' : 'Game in Progress'}
                </p>
                <p className="text-gray-400 text-xs">
                  {session.status === 'active'
                    ? 'Play directly in your browser or connect via SSH'
                    : 'Your game is currently active'}
                </p>
              </div>

              {/* Play in Browser Button - Primary CTA */}
              {token && (
                <Link
                  to={`/play/${session.id}?token=${encodeURIComponent(token)}`}
                  className="block w-full py-4 px-6 bg-gradient-to-r from-btc-orange to-btc-gold text-dark-bg font-pixel text-sm text-center rounded-lg hover:opacity-90 transition-opacity shadow-lg shadow-btc-orange/20"
                >
                  Play in Browser
                </Link>
              )}

              {/* SSH Alternative */}
              <div className="border-t border-dark-border pt-4">
                <p className="text-xs text-gray-500 mb-3 text-center">
                  Or connect via SSH:
                </p>

                {/* SSH Command */}
                {session.ssh_command && (
                  <div className="bg-dark-bg border border-dark-border rounded p-4 mb-4">
                    <p className="text-xs text-gray-500 mb-2">SSH Command</p>
                    <div className="flex items-center gap-2">
                      <code className="text-pixel-green text-sm flex-1 font-mono">
                        {session.ssh_command}
                      </code>
                      <CopyButton text={session.ssh_command} />
                    </div>
                  </div>
                )}

                {/* Credentials */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-dark-bg border border-dark-border rounded p-3">
                    <p className="text-xs text-gray-500 mb-1">Username</p>
                    <div className="flex items-center gap-2">
                      <code className="text-btc-orange text-sm">{session.username}</code>
                      {session.username && <CopyButton text={session.username} label="Copy" />}
                    </div>
                  </div>
                  <div className="bg-dark-bg border border-dark-border rounded p-3">
                    <p className="text-xs text-gray-500 mb-1">Password</p>
                    <div className="flex items-center gap-2">
                      <code className="text-btc-orange text-sm">
                        {session.password?.slice(0, 8)}...
                      </code>
                      {session.password && <CopyButton text={session.password} label="Copy" />}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Ended */}
          {session.status === 'ended' && (
            <div className="bg-gray-800/50 border border-gray-600 rounded p-4 text-center">
              <p className="text-gray-400 text-sm mb-2">Session Ended</p>
              <p className="text-gray-500 text-xs mb-4">
                This game session has ended. Check the leaderboard to see results.
              </p>
              <div className="flex gap-4 justify-center">
                <Link to="/stats" className="btn-secondary text-xs">
                  View Leaderboard
                </Link>
                <Link to="/play" className="btn-primary text-xs">
                  Play Again
                </Link>
              </div>
            </div>
          )}

          {/* Session Info */}
          <div className="border-t border-dark-border pt-4 mt-4">
            <h3 className="font-pixel text-gray-500 text-xs mb-3">Session Info</h3>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-500">Ante Paid</dt>
              <dd className="text-btc-gold">{session.ante_sats.toLocaleString()} sats</dd>

              {session.lightning_address && (
                <>
                  <dt className="text-gray-500">Payout Address</dt>
                  <dd className="text-gray-400 truncate">{session.lightning_address}</dd>
                </>
              )}

              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-400">
                {new Date(session.created_at).toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>
      </div>

      {/* Bookmark notice */}
      <p className="text-center text-gray-600 text-xs mt-6">
        Bookmark this page to check your session status later
      </p>
    </div>
  );
}
