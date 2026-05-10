import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import GamePage from "./pages/GamePage";
import IngestRunsPage from "./pages/IngestRunsPage";
import AgentRunsPage from "./pages/AgentRunsPage";
import NLQueryPage from "./pages/NLQueryPage";
import OperatorPage from "./pages/OperatorPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/games/:id" element={<GamePage />} />
        <Route path="/ingest-runs" element={<IngestRunsPage />} />
        <Route path="/agent-runs" element={<AgentRunsPage />} />
        <Route path="/query" element={<NLQueryPage />} />
        <Route path="/operator" element={<OperatorPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
