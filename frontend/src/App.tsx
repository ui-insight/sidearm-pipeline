import { BrowserRouter, Route, Routes } from "react-router-dom";
import AuthenticationBoundary from "./components/AuthenticationBoundary";
import AppShell from "./components/AppShell";
import HomePage from "./pages/HomePage";
import GamePage from "./pages/GamePage";
import IdentityQueuePage from "./pages/IdentityQueuePage";
import HistoricalBackfillPage from "./pages/HistoricalBackfillPage";
import RecordBookPage from "./pages/RecordBookPage";

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
              <Route path="/record-book" element={<RecordBookPage />} />
              <Route path="/identity-queue" element={<IdentityQueuePage />} />
              <Route path="/backfills" element={<HistoricalBackfillPage />} />
            </Routes>
          </AppShell>
        )}
      </AuthenticationBoundary>
    </BrowserRouter>
  );
}

export default App;
