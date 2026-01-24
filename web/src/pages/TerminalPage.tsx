import { useState, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Terminal, TerminalHandle } from '@/components/Terminal';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export function TerminalPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [error, setError] = useState<string | null>(null);
  const terminalRef = useRef<TerminalHandle>(null);

  const id = sessionId ? parseInt(sessionId, 10) : null;
  const token = searchParams.get('token');

  if (!id || isNaN(id)) {
    return (
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="text-center">
          <p className="text-pixel-red mb-4">Invalid session ID</p>
          <Link to="/play" className="btn-primary text-xs">
            Start New Game
          </Link>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="text-center">
          <p className="text-pixel-red mb-4">Missing access token</p>
          <p className="text-gray-400 text-sm mb-4">
            Please use the link provided in your payment confirmation.
          </p>
          <Link to="/play" className="btn-primary text-xs">
            Start New Game
          </Link>
        </div>
      </div>
    );
  }

  const handleConnect = () => {
    setStatus('connected');
  };

  const handleDisconnect = () => {
    setStatus('disconnected');
  };

  const handleError = (errorMsg: string) => {
    setError(errorMsg);
    setStatus('error');
  };

  const handleBack = () => {
    // Disconnect SSH before navigating to avoid lingering connections
    terminalRef.current?.disconnect();
    navigate(`/session/${id}?token=${encodeURIComponent(token)}`);
  };

  return (
    <div className="fixed inset-0 bg-[#0d0d0d] flex flex-col">
      {/* Minimal header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-dark-surface border-b border-dark-border">
        <div className="flex items-center gap-3">
          <span className="text-btc-orange font-pixel text-xs">
            Orange Nethack
          </span>
          <span className={`text-xs px-2 py-0.5 rounded ${
            status === 'connecting' ? 'bg-yellow-900/50 text-yellow-500' :
            status === 'connected' ? 'bg-green-900/50 text-pixel-green' :
            status === 'error' ? 'bg-red-900/50 text-pixel-red' :
            'bg-gray-800 text-gray-400'
          }`}>
            {status === 'connecting' ? 'Connecting...' :
             status === 'connected' ? 'Connected' :
             status === 'error' ? 'Error' :
             'Disconnected'}
          </span>
        </div>
        <button
          onClick={handleBack}
          className="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1 rounded hover:bg-dark-bg"
        >
          Back to Session
        </button>
      </div>

      {/* Terminal area */}
      <div className="flex-1 relative">
        {status === 'disconnected' || status === 'error' ? (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d0d0d]">
            <div className="text-center">
              {error && (
                <p className="text-pixel-red mb-4">{error}</p>
              )}
              <p className="text-gray-400 mb-6">
                {status === 'error'
                  ? 'Connection failed. Please try again.'
                  : 'Connection closed.'}
              </p>
              <div className="flex gap-4 justify-center">
                <button
                  onClick={() => window.location.reload()}
                  className="btn-primary text-xs"
                >
                  Reconnect
                </button>
                <button
                  onClick={handleBack}
                  className="btn-secondary text-xs"
                >
                  Back to Session
                </button>
              </div>
            </div>
          </div>
        ) : (
          <Terminal
            ref={terminalRef}
            sessionId={id}
            token={token}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            onError={handleError}
          />
        )}
      </div>

      {/* Footer hint */}
      <div className="px-4 py-1 bg-dark-surface border-t border-dark-border text-center">
        <p className="text-gray-600 text-xs">
          Use <kbd className="px-1 bg-dark-bg rounded">h j k l y u b n</kbd> to move
          {' '}&bull;{' '}
          <kbd className="px-1 bg-dark-bg rounded">?</kbd> for help
          {' '}&bull;{' '}
          <kbd className="px-1 bg-dark-bg rounded">S</kbd> to save &amp; quit
        </p>
      </div>
    </div>
  );
}
