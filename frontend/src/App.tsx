import { BrowserRouter, Route, Routes } from "react-router";
import AuthenticationBoundary from "./components/AuthenticationBoundary";
import AppShell from "./components/AppShell";
import ProjectOverviewPage from "./pages/ProjectOverviewPage";
import GamesDeskPage from "./pages/GamesDeskPage";
import GamePage from "./pages/GamePage";
import IdentityQueuePage from "./pages/IdentityQueuePage";
import HistoricalBackfillPage from "./pages/HistoricalBackfillPage";
import RecordBookPage from "./pages/RecordBookPage";
import ExploratoryWorkspacePage from "./pages/ExploratoryWorkspacePage";
import PlayerComparisonPage from "./pages/PlayerComparisonPage";
import AthleticsDemoPage from "./pages/AthleticsDemoPage";
import AchievementReviewPage from "./pages/AchievementReviewPage";
import AskWarehousePage from "./pages/AskWarehousePage";
import ArticleBriefPage from "./pages/ArticleBriefPage";
import ArticleQueuePage from "./pages/ArticleQueuePage";
import AccessDeniedPage from "./pages/AccessDeniedPage";
import StyleGuidesPage from "./pages/StyleGuidesPage";

function App() {
  return (
    <BrowserRouter>
      <AuthenticationBoundary>
        {({ username, roles, logoutPending, logoutError, onLogout }) => (
          <AppShell
            username={username}
            roles={roles}
            logoutPending={logoutPending}
            logoutError={logoutError}
            onLogout={onLogout}
          >
            <Routes>
              <Route path="/" element={<ProjectOverviewPage />} />
              <Route path="/games" element={<GamesDeskPage />} />
              <Route path="/games/:id" element={<GamePage />} />
              <Route path="/workspace" element={<ExploratoryWorkspacePage />} />
              <Route path="/ask" element={<AskWarehousePage />} />
              <Route path="/workspace/compare" element={<PlayerComparisonPage />} />
              <Route path="/record-book" element={<RecordBookPage />} />
              <Route path="/achievements" element={<AchievementReviewPage />} />
              <Route path="/articles" element={<ArticleQueuePage />} />
              <Route path="/articles/:id" element={<ArticleBriefPage />} />
              <Route
                path="/style-guides"
                element={
                  roles.includes("style_steward") ? (
                    <StyleGuidesPage />
                  ) : (
                    <AccessDeniedPage />
                  )
                }
              />
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
