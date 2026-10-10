export { previewDataProvider } from "@/services/previewDataProvider";
export type {
  MarketDataProvider,
  DecisionService,
  ReceiptVerificationService,
} from "@/services/marketDataProvider";

/**
 * Service wiring for the frontend.
 *
 * Today: the deterministic preview provider. Tomorrow: a real API provider
 * implementing the same interfaces. Presentation components import from
 * this module only, so the swap is a one-line change.
 */
import { liveDataProvider as provider } from "@/services/liveDataProvider";

export const dataProvider = provider;
