import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { LandingPage } from '@/pages/LandingPage';
import { PlayPage } from '@/pages/PlayPage';
import { StatsPage } from '@/pages/StatsPage';
import { SessionPage } from '@/pages/SessionPage';
import { TerminalPage } from '@/pages/TerminalPage';

function App() {
  return (
    <Routes>
      {/* Terminal page is full-screen, no layout */}
      <Route path="/play/:sessionId" element={<TerminalPage />} />

      {/* Regular pages with layout */}
      <Route element={<Layout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/play" element={<PlayPage />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/session/:sessionId" element={<SessionPage />} />
      </Route>
    </Routes>
  );
}

export default App;
