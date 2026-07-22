import CatalogDetailPage from "../components/CatalogDetailPage";
import { CATALOG_KINDS } from "../catalog/kinds";

export default function EventPage() {
  return <CatalogDetailPage kind={CATALOG_KINDS.event} />;
}
