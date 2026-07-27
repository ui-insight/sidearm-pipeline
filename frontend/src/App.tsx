import { BrowserRouter, Route, Routes } from "react-router";
import AuthenticationBoundary from "./components/AuthenticationBoundary";
import AppShell from "./components/AppShell";
import HomePage from "./pages/HomePage";
import GamePage from "./pages/GamePage";
import IdentityQueuePage from "./pages/IdentityQueuePage";
import HistoricalBackfillPage from "./pages/HistoricalBackfillPage";
import RecordBookPage from "./pages/RecordBookPage";
import ExploratoryWorkspacePage from "./pages/ExploratoryWorkspacePage";
import PlayerComparisonPage from "./pages/PlayerComparisonPage";
import AthleticsDemoPage from "./pages/AthleticsDemoPage";
import AchievementReviewPage from "./pages/AchievementReviewPage";
import AskWarehousePage from "./pages/AskWarehousePage";

function App() {
  return (
    <BrowserRouter>
      <AuthenticationBoundary>
        {({ username, logoutPending, logoutError, onLogout }) => (
          <AppShell
            username={username}
            logoutPending={logoutPending}
            logoutError={logoutError}
            onLogout={onLogout}
          >
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/games/:id" element={<GamePage />} />
              <Route path="/workspace" element={<ExploratoryWorkspacePage />} />
              <Route path="/ask" element={<AskWarehousePage />} />
              <Route path="/workspace/compare" element={<PlayerComparisonPage />} />
              <Route path="/record-book" element={<RecordBookPage />} />
              <Route path="/achievements" element={<AchievementReviewPage />} />
              <Route path="/identity-queue" element={<IdentityQueuePage />} />
              <Route path="/backfills" element={<HistoricalBackfillPage />} />
              <Route path="/demo" element={<AthleticsDemoPage />} />
            </Routes>
          </AppShell>
        )}
      </AuthenticationBoundary>
    </BrowserRouter>
  );
}

export default App;
