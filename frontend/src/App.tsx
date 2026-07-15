import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import HomePage from "./pages/HomePage";
import GamePage from "./pages/GamePage";
import IdentityQueuePage from "./pages/IdentityQueuePage";

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/games/:id" element={<GamePage />} />
          <Route path="/identity-queue" element={<IdentityQueuePage />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
