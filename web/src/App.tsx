import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { LandingPage } from '@/pages/LandingPage';
import { PlayPage } from '@/pages/PlayPage';
import { StatsPage } from '@/pages/StatsPage';
import { SessionPage } from '@/pages/SessionPage';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/play" element={<PlayPage />} />
        <Route path="/stats" element={<StatsPage />} />
        <Route path="/session/:sessionId" element={<SessionPage />} />
      </Routes>
    </Layout>
  );
}

export default App;
