import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  type BrowseCatalogEntity,
  type BrowseSection,
  type Edit,
  type Video,
} from "../api";
import CatalogBrowseCard from "../components/CatalogBrowseCard";
import OpenEditCard from "../components/OpenEditCard";
import VideoCard from "../components/VideoCard";

const VIDEO_SECTION_FILTERS: Record<
  string,
  {
    title: string;
    opts: {
      commercial_type?: string;
      channel_commercials?: boolean;
      sort?: "created_at" | "updated_at";
      updated_only?: boolean;
      main_only?: boolean;
    };
  }
> = {
  newly_added: { title: "Newly added", opts: { sort: "created_at" } },
  updated: {
    title: "Recently updated",
    opts: { sort: "updated_at", updated_only: true },
  },
  psa: { title: "PSAs", opts: { commercial_type: "psa", main_only: true } },
  general_ad: {
    title: "General ads",
    opts: { commercial_type: "general_ad", main_only: true },
  },
  service: {
    title: "Service commercials",
    opts: { commercial_type: "service", main_only: true },
  },
  store: {
    title: "Store commercials",
    opts: { commercial_type: "store", main_only: true },
  },
  bumper: { title: "Bumpers", opts: { commercial_type: "bumper", main_only: true } },
  spoof: { title: "Spoofs", opts: { commercial_type: "spoof", main_only: true } },
  channel_commercial: {
    title: "Channel commercials",
    opts: { channel_commercials: true, main_only: true },
  },
};

const CATALOG_SECTION_FILTERS: Record<
  string,
  {
    title: string;
    catalogKey: "brand" | "store" | "service" | "event" | "holiday";
    opts: { sort: "created_at" | "updated_at"; updated_only?: boolean };
  }
> = {
  new_brands: { title: "New brands", catalogKey: "brand", opts: { sort: "created_at" } },
  updated_brands: {
    title: "Updated brands",
    catalogKey: "brand",
    opts: { sort: "updated_at", updated_only: true },
  },
  new_stores: { title: "New stores", catalogKey: "store", opts: { sort: "created_at" } },
  updated_stores: {
    title: "Updated stores",
    catalogKey: "store",
    opts: { sort: "updated_at", updated_only: true },
  },
  new_services: { title: "New services", catalogKey: "service", opts: { sort: "created_at" } },
  updated_services: {
    title: "Updated services",
    catalogKey: "service",
    opts: { sort: "updated_at", updated_only: true },
  },
  new_events: { title: "New events", catalogKey: "event", opts: { sort: "created_at" } },
  updated_events: {
    title: "Updated events",
    catalogKey: "event",
    opts: { sort: "updated_at", updated_only: true },
  },
  new_holidays: { title: "New holidays", catalogKey: "holiday", opts: { sort: "created_at" } },
  updated_holidays: {
    title: "Updated holidays",
    catalogKey: "holiday",
    opts: { sort: "updated_at", updated_only: true },
  },
};

function BrowseRow({ section }: { section: BrowseSection }) {
  if (section.kind === "edits") {
    const edits = section.items as Edit[];
    return (
      <section className="browse-row">
        <div className="browse-row-header">
          <h2 className="browse-row-title">{section.title}</h2>
          {section.see_all_path && (
            <Link to={section.see_all_path} className="muted">
              See all{section.total > edits.length ? ` (${section.total})` : ""} →
            </Link>
          )}
        </div>
        {edits.length === 0 ? (
          <p className="muted">No open submissions right now.</p>
        ) : (
          <div className="browse-row-scroller">
            {edits.map((edit) => (
              <div key={edit.id} className="browse-row-item browse-row-item-edit">
                <OpenEditCard edit={edit} />
              </div>
            ))}
          </div>
        )}
      </section>
    );
  }

  if (section.kind === "catalog") {
    const entities = section.items as BrowseCatalogEntity[];
    if (entities.length === 0) return null;
    return (
      <section className="browse-row">
        <div className="browse-row-header">
          <h2 className="browse-row-title">{section.title}</h2>
          {section.see_all_path && (
            <Link to={section.see_all_path} className="muted">
              See all{section.total > entities.length ? ` (${section.total})` : ""} →
            </Link>
          )}
        </div>
        <div className="browse-row-scroller">
          {entities.map((entity) => (
            <div key={entity.sbid} className="browse-row-item browse-row-item-catalog">
              <CatalogBrowseCard entity={entity} />
            </div>
          ))}
        </div>
      </section>
    );
  }

  const videos = section.items as Video[];
  if (videos.length === 0) return null;

  return (
    <section className="browse-row">
      <div className="browse-row-header">
        <h2 className="browse-row-title">{section.title}</h2>
        {section.see_all_path && (
          <Link to={section.see_all_path} className="muted">
            See all{section.total > videos.length ? ` (${section.total})` : ""} →
          </Link>
        )}
      </div>
      <div className="browse-row-scroller">
        {videos.map((video) => (
          <div key={video.sbid} className="browse-row-item">
            <VideoCard video={video} />
          </div>
        ))}
      </div>
    </section>
  );
}

function VideoSectionGrid({ sectionId }: { sectionId: string }) {
  const config = VIDEO_SECTION_FILTERS[sectionId];
  const { data, isLoading, error } = useQuery({
    queryKey: ["browse-section", sectionId],
    queryFn: () => api.browseVideos(0, 48, config.opts),
    enabled: !!config,
  });

  if (!config) return <p className="error">Unknown browse section.</p>;
  if (isLoading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  return (
    <div>
      <div className="browse-row-header" style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          {config.title}
        </h1>
        <Link to="/browse" className="muted">
          ← All shelves
        </Link>
      </div>
      <div className="video-grid">
        {(data?.items ?? []).map((video) => (
          <VideoCard key={video.sbid} video={video} />
        ))}
      </div>
      {data?.items.length === 0 && <p className="muted">Nothing in this shelf yet.</p>}
    </div>
  );
}

function CatalogSectionGrid({ sectionId }: { sectionId: string }) {
  const config = CATALOG_SECTION_FILTERS[sectionId];
  const { data, isLoading, error } = useQuery({
    queryKey: ["browse-catalog-section", sectionId],
    queryFn: () => api.browseCatalog(config.catalogKey, 0, 48, config.opts),
    enabled: !!config,
  });

  if (!config) return <p className="error">Unknown browse section.</p>;
  if (isLoading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  return (
    <div>
      <div className="browse-row-header" style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          {config.title}
        </h1>
        <Link to="/browse" className="muted">
          ← All shelves
        </Link>
      </div>
      <div className="catalog-browse-grid">
        {(data?.items ?? []).map((entity) => (
          <CatalogBrowseCard key={entity.sbid} entity={entity} />
        ))}
      </div>
      {data?.items.length === 0 && <p className="muted">Nothing in this shelf yet.</p>}
    </div>
  );
}

export default function BrowsePage() {
  const [searchParams] = useSearchParams();
  const sectionId = searchParams.get("section");

  const { data, isLoading, error } = useQuery({
    queryKey: ["browse-sections"],
    queryFn: () => api.browseSections(16),
    enabled: !sectionId || sectionId === "needs_votes",
  });

  if (sectionId === "needs_votes") {
    return (
      <div>
        <div className="browse-row-header" style={{ marginBottom: "1rem" }}>
          <h1 className="page-title" style={{ margin: 0 }}>
            Needs votes
          </h1>
          <Link to="/voting" className="muted">
            Full voting queue →
          </Link>
        </div>
        {isLoading && <p className="muted">Loading…</p>}
        {error && <p className="error">{(error as Error).message}</p>}
        <div className="stack">
          {((data?.sections.find((s) => s.id === "needs_votes")?.items as Edit[]) ?? []).map(
            (edit) => (
              <OpenEditCard key={edit.id} edit={edit} />
            )
          )}
        </div>
      </div>
    );
  }

  if (sectionId && CATALOG_SECTION_FILTERS[sectionId]) {
    return <CatalogSectionGrid sectionId={sectionId} />;
  }

  if (sectionId && VIDEO_SECTION_FILTERS[sectionId]) {
    return <VideoSectionGrid sectionId={sectionId} />;
  }

  if (isLoading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">{(error as Error).message}</p>;

  const sections = data?.sections ?? [];

  return (
    <div className="browse-home">
      <h1 className="page-title">Browse</h1>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        Shelves of videos and catalog entries — vote on open edits, then browse by recency and type.
      </p>
      {sections.length === 0 && <p className="muted">Nothing to browse yet.</p>}
      {sections.map((section) => (
        <BrowseRow key={section.id} section={section} />
      ))}
    </div>
  );
}
