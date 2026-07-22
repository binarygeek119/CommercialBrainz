import CatalogDetailPage from "../components/CatalogDetailPage";
import { CATALOG_KINDS } from "../catalog/kinds";

export default function ServicePage() {
  return <CatalogDetailPage kind={CATALOG_KINDS.service} />;
}
