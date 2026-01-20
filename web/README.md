# Orange Nethack Web UI

React + TypeScript frontend for Orange Nethack with pixel art aesthetic and Bitcoin orange accents.

## Status: MVP Complete

The core frontend is implemented and building successfully.

## Tech Stack

- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS
- **Fonts**: Press Start 2P (pixel), JetBrains Mono (code)
- **QR Codes**: qrcode.react

## Project Structure

```
web/
├── src/
│   ├── api/client.ts           # Type-safe API client
│   ├── components/             # Reusable UI components
│   │   ├── Layout.tsx          # App shell with nav
│   │   ├── PotDisplay.tsx      # Pot balance with polling
│   │   ├── CopyButton.tsx      # Clipboard copy
│   │   ├── StatusBadge.tsx     # Session status badges
│   │   ├── LoadingSpinner.tsx  # Loading indicators
│   │   └── AsciiLogo.tsx       # ASCII art decorations
│   ├── hooks/                  # Custom React hooks
│   │   ├── usePot.ts           # Pot balance polling
│   │   ├── useStats.ts         # Stats/leaderboard polling
│   │   ├── useSession.ts       # Session status polling
│   │   └── useCopyToClipboard.ts
│   ├── pages/
│   │   ├── LandingPage.tsx     # Hero, pot, how to play, FAQ
│   │   ├── PlayPage.tsx        # 3-step: form → QR → credentials
│   │   ├── StatsPage.tsx       # Leaderboard tables
│   │   └── SessionPage.tsx     # Session status checker
│   ├── types/api.ts            # TypeScript API types
│   ├── App.tsx                 # Router setup
│   ├── main.tsx                # Entry point
│   └── index.css               # Tailwind + custom styles
├── public/orange.svg           # Favicon
└── [config files]
```

## Development

```bash
# Install dependencies
npm install

# Run dev server (proxies /api to localhost:8000)
npm run dev

# Build for production
npm run build
```

## What's Done

- [x] Vite + React + TypeScript + Tailwind scaffold
- [x] API client with TypeScript types
- [x] Landing page (hero, pot display, how to play, FAQ)
- [x] Play flow (form → Lightning QR → SSH credentials)
- [x] Leaderboard page (stats, high scores, recent games, ascensions)
- [x] Session status page
- [x] Pixel art styling (colors, fonts, ASCII art)
- [x] Backend static file serving (in api/main.py)
- [x] Dockerfile multi-stage build
- [x] ttyrec recording for spectator prep (in orange-shell.sh)

## Future Enhancements (Not Started)

- [ ] Live spectator mode (xterm.js + WebSocket + ttyrec playback)
- [ ] User accounts / profiles
- [ ] Tournament system
- [ ] Real-time pot updates (WebSocket instead of polling)
- [ ] Game replays from ttyrec files

## Backend Integration

The FastAPI backend serves the built frontend from `web/dist/`. CORS is already configured. The Dockerfile builds the frontend in a Node.js stage, then copies `dist/` to the final image.

## Color Palette

- Background: `#0a0a0a`
- BTC Orange: `#f7931a`
- BTC Gold: `#ffd700`
- Pixel Green: `#00ff00`
- Pixel Red: `#ff4444`
