import type { CommercialDetail, Video } from "../api";
import type { RegionSelection } from "../components/RegionPicker";
import {
  EMPTY_SUBMISSION_GENRES,
  genresFromMetadata,
  type SubmissionGenres,
} from "./submissionGenres";
import { formatCommercialPeriod } from "./commercialPeriod";

export interface AddLinkFormDefaults {
  language: string;
  slogan: string;
  transcript: string;
  tags: string;
  regionSelection: RegionSelection;
  genres: SubmissionGenres;
  referenceVideoSbid: string | null;
  referenceLabel: string | null;
}

export const EMPTY_ADD_LINK_DEFAULTS: AddLinkFormDefaults = {
  language: "",
  slogan: "",
  transcript: "",
  tags: "",
  regionSelection: {},
  genres: { ...EMPTY_SUBMISSION_GENRES },
  referenceVideoSbid: null,
  referenceLabel: null,
};

export function referenceVideoFromCommercial(commercial: CommercialDetail): Video | null {
  const videos = commercial.videos ?? [];
  if (!videos.length) return null;
  return videos.find((v) => v.is_main) ?? videos[0];
}

export function addLinkDefaultsFromVideo(video: Video): Omit<
  AddLinkFormDefaults,
  "referenceVideoSbid" | "referenceLabel"
> {
  const genres = genresFromMetadata(video.metadata?.genres);
  return {
    language: video.language ?? "",
    slogan: video.slogan ?? "",
    transcript: video.transcript ?? "",
    tags: (video.tags ?? []).join(", "),
    regionSelection: {
      region: video.region ?? undefined,
      sub_region: video.sub_region ?? undefined,
    },
    genres,
  };
}

export function commercialInheritanceSummary(commercial: CommercialDetail): string[] {
  const lines = [commercial.title];
  if (commercial.advertiser?.name) lines.push(`Brand: ${commercial.advertiser.name}`);
  const period = formatCommercialPeriod(commercial.year, commercial.decade);
  if (period) lines.push(`Aired: ${period}`);
  if (commercial.products?.length) lines.push(`Products: ${commercial.products.join(", ")}`);
  return lines;
}
