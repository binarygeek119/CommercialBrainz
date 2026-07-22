import CatalogListPage from "../components/CatalogListPage";
import { CATALOG_KINDS } from "../catalog/kinds";

export default function StoresPage() {
  return <CatalogListPage kind={CATALOG_KINDS.store} />;
}
