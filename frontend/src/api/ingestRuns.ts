import { api } from "./client";
import type { IngestRun } from "../types/ingestRun";

export const ingestRunsApi = {
  listHistoricalWbbRanges: () =>
    api.get<IngestRun[]>("/ingest-runs", {
      source_type: "historical_range_backfill",
      sport: "womens-basketball",
      limit: "10",
    }),
};
