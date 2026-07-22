import CatalogListPage from "../components/CatalogListPage";
import { CATALOG_KINDS } from "../catalog/kinds";

export default function EventsPage() {
  return <CatalogListPage kind={CATALOG_KINDS.event} />;
}
