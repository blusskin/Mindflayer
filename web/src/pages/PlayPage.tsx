import { useState } from 'react';
import { Link } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '@/api/client';
import { useSession } from '@/hooks/useSession';
import { usePot } from '@/hooks/usePot';
import { CopyButton } from '@/components/CopyButton';
import { StatusBadge } from '@/components/StatusBadge';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import type { InvoiceResponse, PlayRequest } from '@/types/api';

type Step = 'configure' | 'payment' | 'credentials';

export function PlayPage() {
  const [step, setStep] = useState<Step>('configure');
  const [invoice, setInvoice] = useState<InvoiceResponse | null>(null);
  const [formData, setFormData] = useState<PlayRequest>({
    lightning_address: '',
    email: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { pot } = usePot();
  const { session } = useSession(invoice?.session_id ?? null, invoice?.access_token ?? null, {
    pollInterval: 2000,
    stopOnActive: true,
  });

  // Move to credentials step when payment is confirmed
  if (session && session.status !== 'pending' && step === 'payment') {
    setStep('credentials');
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const requestData: PlayRequest = {};
      if (formData.lightning_address) requestData.lightning_address = formData.lightning_address;
      if (formData.email) requestData.email = formData.email;

      const result = await api.createSession(requestData);
      setInvoice(result);
      setStep('payment');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInputChange = (field: keyof PlayRequest) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const resetFlow = () => {
    setStep('configure');
    setInvoice(null);
    setError(null);
    setFormData({ lightning_address: '', email: '' });
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Progress Steps */}
      <div className="flex items-center justify-center mb-8">
        {(['configure', 'payment', 'credentials'] as Step[]).map((s, i) => {
          const steps: Step[] = ['configure', 'payment', 'credentials'];
          const currentStepIndex = steps.indexOf(step);
          return (
          <div key={s} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-pixel text-xs ${
                step === s
                  ? 'bg-btc-orange text-dark-bg'
                  : currentStepIndex > i
                    ? 'bg-pixel-green/20 text-pixel-green border border-pixel-green'
                    : 'bg-dark-surface text-gray-500 border border-dark-border'
              }`}
            >
              {i + 1}
            </div>
            {i < 2 && (
              <div
                className={`w-12 sm:w-24 h-0.5 ${
                  currentStepIndex > i ? 'bg-pixel-green' : 'bg-dark-border'
                }`}
              />
            )}
          </div>
        );
        })}
      </div>

      {/* Step 1: Configure */}
      {step === 'configure' && (
        <div className="card-glow">
          <h1 className="font-pixel text-btc-orange text-sm mb-2 text-center">
            Start a New Game
          </h1>
          <p className="text-gray-400 text-sm text-center mb-6">
            Ante: <span className="text-btc-gold">{pot?.ante_sats.toLocaleString() ?? '...'} sats</span>
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Lightning Address <span className="text-gray-600">(for payout)</span>
              </label>
              <input
                type="text"
                placeholder="you@getalby.com"
                value={formData.lightning_address}
                onChange={handleInputChange('lightning_address')}
                className="input w-full"
              />
              <p className="text-xs text-gray-500 mt-1">
                Receive the pot if you ascend. Can be set later.
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Email <span className="text-gray-600">(optional)</span>
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={formData.email}
                onChange={handleInputChange('email')}
                className="input w-full"
              />
              <p className="text-xs text-gray-500 mt-1">
                Receive payment confirmation and game results.
              </p>
            </div>

            {error && (
              <div className="bg-pixel-red/20 border border-pixel-red text-pixel-red p-3 rounded text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <LoadingSpinner size="sm" />
                  Creating Session...
                </>
              ) : (
                <>Get Invoice</>
              )}
            </button>
          </form>
        </div>
      )}

      {/* Step 2: Payment */}
      {step === 'payment' && invoice && (
        <div className="card-glow text-center">
          <h1 className="font-pixel text-btc-orange text-sm mb-2">
            Pay the Ante
          </h1>
          <p className="text-gray-400 text-sm mb-6">
            Scan the QR code or copy the invoice
          </p>

          {/* QR Code */}
          <div className="qr-container mx-auto mb-6">
            <QRCodeSVG
              value={invoice.payment_request}
              size={200}
              level="M"
              fgColor="#f7931a"
            />
          </div>

          {/* Invoice string */}
          <div className="bg-dark-bg border border-dark-border rounded p-3 mb-4">
            <p className="text-xs text-gray-500 mb-2">Lightning Invoice</p>
            <p className="text-xs font-mono text-gray-400 break-all mb-2">
              {invoice.payment_request.slice(0, 60)}...
            </p>
            <CopyButton text={invoice.payment_request} label="Copy Invoice" />
          </div>

          {/* Amount */}
          <div className="text-sm text-gray-400 mb-4">
            Amount: <span className="text-btc-gold">{invoice.amount_sats.toLocaleString()} sats</span>
          </div>

          {/* Waiting indicator */}
          <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
            <LoadingSpinner size="sm" />
            <span>Waiting for payment...</span>
          </div>

          {/* Session ID for reference */}
          <p className="text-xs text-gray-600 mt-4">
            Session ID: {invoice.session_id}
          </p>

          <button
            onClick={resetFlow}
            className="text-xs text-gray-500 hover:text-btc-orange mt-4 underline"
          >
            Cancel and start over
          </button>
        </div>
      )}

      {/* Step 3: Credentials */}
      {step === 'credentials' && session && (
        <div className="card-glow">
          <div className="text-center mb-6">
            <div className="text-4xl mb-4">🎮</div>
            <h1 className="font-pixel text-pixel-green text-sm mb-2">
              Payment Received!
            </h1>
            <p className="text-gray-400 text-sm">
              Your game is ready. Play in your browser or connect via SSH.
            </p>
          </div>

          <div className="space-y-4">
            {/* Status */}
            <div className="flex items-center justify-between">
              <span className="text-gray-400 text-sm">Status:</span>
              <StatusBadge status={session.status} />
            </div>

            {/* Play in Browser Button - Primary CTA */}
            <Link
              to={`/play/${session.id}?token=${encodeURIComponent(invoice?.access_token ?? '')}`}
              className="block w-full py-4 px-6 bg-gradient-to-r from-btc-orange to-btc-gold text-dark-bg font-pixel text-sm text-center rounded-lg hover:opacity-90 transition-opacity shadow-lg shadow-btc-orange/20"
            >
              Play in Browser
            </Link>

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

            {/* Tips */}
            <div className="bg-btc-orange/10 border border-btc-orange/30 rounded p-4 text-sm">
              <p className="text-btc-orange font-pixel text-xs mb-2">Quick Tips</p>
              <ul className="text-gray-400 text-xs space-y-1">
                <li>• Press <span className="text-btc-gold">?</span> for help at any time</li>
                <li>• Your pet <span className="text-pixel-green">d</span> can help you fight</li>
                <li>• Press <span className="text-btc-gold">S</span> to save and quit (you can resume later)</li>
                <li>• Ascend to win the pot!</li>
              </ul>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
              <button onClick={resetFlow} className="btn-secondary flex-1 text-xs">
                Play Again
              </button>
              <a href="/stats" className="btn-primary flex-1 text-xs text-center">
                Leaderboard
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
