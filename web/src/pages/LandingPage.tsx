import { Link } from 'react-router-dom';
import { PotDisplay } from '@/components/PotDisplay';
import { AsciiLogo, AsciiDungeon } from '@/components/AsciiLogo';

export function LandingPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Hero Section */}
      <section className="text-center py-8 sm:py-16">
        <AsciiLogo className="hidden sm:block mb-8" />
        <h1 className="font-pixel text-btc-orange text-xl sm:text-2xl sm:hidden mb-4">
          🍊 Orange Nethack ⚡
        </h1>

        <p className="text-gray-400 text-sm sm:text-base max-w-xl mx-auto mb-8">
          The classic roguelike with Bitcoin Lightning payments.
          <br />
          <span className="text-btc-gold">Ascend and win the entire pot!</span>
        </p>

        {/* Pot Display */}
        <div className="card-glow inline-block px-8 sm:px-16 py-6 mb-8">
          <PotDisplay size="lg" />
        </div>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/play" className="btn-primary text-sm">
            Play Now
          </Link>
          <Link to="/stats" className="btn-secondary text-sm">
            View Leaderboard
          </Link>
        </div>
      </section>

      {/* How to Play */}
      <section className="py-8 sm:py-12">
        <h2 className="font-pixel text-btc-orange text-sm sm:text-base text-center mb-8">
          How to Play
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="card text-center">
            <div className="text-3xl mb-4">⚡</div>
            <h3 className="font-pixel text-btc-gold text-xs mb-3">1. Pay the Ante</h3>
            <p className="text-gray-400 text-sm">
              Pay a small Lightning invoice to enter the dungeon. Your ante goes into the pot.
            </p>
          </div>

          <div className="card text-center">
            <div className="text-3xl mb-4">💻</div>
            <h3 className="font-pixel text-btc-gold text-xs mb-3">2. SSH In</h3>
            <p className="text-gray-400 text-sm">
              Receive unique SSH credentials. Connect and play Nethack in your terminal.
            </p>
          </div>

          <div className="card text-center">
            <div className="text-3xl mb-4">🏆</div>
            <h3 className="font-pixel text-btc-gold text-xs mb-3">3. Ascend to Win</h3>
            <p className="text-gray-400 text-sm">
              Complete the game by ascending. Winner takes the entire pot via Lightning!
            </p>
          </div>
        </div>
      </section>

      {/* ASCII Art Decoration */}
      <section className="py-8 hidden sm:block">
        <AsciiDungeon />
      </section>

      {/* What is Nethack */}
      <section className="py-8 sm:py-12">
        <h2 className="font-pixel text-btc-orange text-sm sm:text-base text-center mb-8">
          What is Nethack?
        </h2>

        <div className="card max-w-2xl mx-auto">
          <p className="text-gray-400 text-sm leading-relaxed mb-4">
            <span className="text-btc-orange">NetHack</span> is one of the oldest and most
            influential roguelike games ever made. First released in 1987, it challenges
            players to descend through randomly generated dungeon levels, retrieve the
            Amulet of Yendor, and ascend to godhood.
          </p>
          <p className="text-gray-400 text-sm leading-relaxed mb-4">
            The game is famous for its incredible depth, complexity, and the principle that
            <span className="text-btc-gold"> "The DevTeam Thinks of Everything"</span>.
            Every run is unique, and permadeath means your choices matter.
          </p>
          <p className="text-gray-500 text-xs">
            Fun fact: Less than 1% of players have ever ascended. Will you be one of them?
          </p>
        </div>
      </section>

      {/* Quick Tips */}
      <section className="py-8 sm:py-12">
        <h2 className="font-pixel text-btc-orange text-sm sm:text-base text-center mb-8">
          Quick Tips
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto">
          <div className="card border-l-4 border-l-btc-orange">
            <p className="text-sm">
              <span className="text-btc-orange">@</span> is you.
              <span className="text-pixel-green"> d</span> is a dog (pet!).
              <span className="text-pixel-red"> D</span> is a dragon (run!).
            </p>
          </div>
          <div className="card border-l-4 border-l-btc-orange">
            <p className="text-sm">
              Press <span className="text-btc-gold">?</span> for help,
              <span className="text-btc-gold"> i</span> for inventory,
              <span className="text-btc-gold"> ;</span> to look around.
            </p>
          </div>
          <div className="card border-l-4 border-l-btc-orange">
            <p className="text-sm">
              <span className="text-btc-gold">Elbereth</span> written in dust
              can save your life. Use <span className="text-btc-gold">E</span> to engrave.
            </p>
          </div>
          <div className="card border-l-4 border-l-btc-orange">
            <p className="text-sm">
              Don't touch <span className="text-pixel-red">cockatrice</span> corpses
              without gloves. Trust us.
            </p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-8 sm:py-12">
        <h2 className="font-pixel text-btc-orange text-sm sm:text-base text-center mb-8">
          FAQ
        </h2>

        <div className="space-y-4 max-w-2xl mx-auto">
          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              What happens if I die?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="text-gray-400 text-sm mt-4">
              This is Nethack - death is permanent! Your ante stays in the pot for the next
              brave adventurer. You can always pay another ante to try again.
            </p>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              How do I receive my winnings?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="text-gray-400 text-sm mt-4">
              Provide your Lightning address when starting. If you ascend, the pot is
              automatically sent to your address. You can also set it later via the API.
            </p>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              Is this legitimate Nethack?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="text-gray-400 text-sm mt-4">
              Yes! We run vanilla NetHack 3.6.7. No modifications, no cheats. Your skills
              and luck determine your fate.
            </p>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              What if the invoice expires?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="text-gray-400 text-sm mt-4">
              No problem! Just start a new session and generate a fresh invoice. Unpaid
              sessions are automatically cleaned up.
            </p>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              Do I have a Lightning address?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="text-gray-400 text-sm mt-4 space-y-2">
              <p>If you use any of these apps, you already have a Lightning address:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><span className="text-btc-gold">Cash App</span> — yourname@cash.app (use your $cashtag)</li>
                <li><span className="text-btc-gold">Strike</span> — yourname@strike.me</li>
                <li><span className="text-btc-gold">Wallet of Satoshi</span> — yourname@walletofsatoshi.com</li>
              </ul>
              <p className="text-gray-500 text-xs mt-2">
                Check your app's settings for "Lightning Address" or "Receive" options.
              </p>
            </div>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              Where can I learn more about Nethack?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="text-gray-400 text-sm mt-4 space-y-2">
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>
                  <a href="https://nethackwiki.com" target="_blank" rel="noopener noreferrer" className="text-btc-gold hover:text-btc-orange transition-colors">
                    NetHack Wiki
                  </a> — Comprehensive guides and spoilers
                </li>
                <li>
                  <a href="https://www.nethack.org" target="_blank" rel="noopener noreferrer" className="text-btc-gold hover:text-btc-orange transition-colors">
                    nethack.org
                  </a> — Official Nethack website
                </li>
                <li>
                  <a href="https://www.reddit.com/r/nethack" target="_blank" rel="noopener noreferrer" className="text-btc-gold hover:text-btc-orange transition-colors">
                    r/nethack
                  </a> — Reddit community
                </li>
              </ul>
            </div>
          </details>

          <details className="card group">
            <summary className="cursor-pointer text-btc-gold font-pixel text-xs flex items-center justify-between">
              How do I contact you?
              <span className="text-btc-orange group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <p className="text-gray-400 text-sm mt-4">
              Questions, feedback, or just want to say hi? Email us at{' '}
              <a href="mailto:mindflayer@orangenethack.com" className="text-btc-gold hover:text-btc-orange transition-colors">
                mindflayer@orangenethack.com
              </a>
            </p>
          </details>
        </div>
      </section>
    </div>
  );
}
