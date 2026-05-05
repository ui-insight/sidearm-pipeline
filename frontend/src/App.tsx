import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import GamePage from "./pages/GamePage";
import IngestRunsPage from "./pages/IngestRunsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/games/:id" element={<GamePage />} />
        <Route path="/ingest-runs" element={<IngestRunsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
