export interface SubRegionOption {
  code: string;
  label: string;
}

export interface RegionOption {
  code: string;
  label: string;
  subRegions: SubRegionOption[];
}

export interface RegionGroup {
  label: string;
  regions: RegionOption[];
}

const US_STATES: SubRegionOption[] = [
  { code: "al", label: "Alabama" },
  { code: "ak", label: "Alaska" },
  { code: "az", label: "Arizona" },
  { code: "ar", label: "Arkansas" },
  { code: "ca", label: "California" },
  { code: "co", label: "Colorado" },
  { code: "ct", label: "Connecticut" },
  { code: "de", label: "Delaware" },
  { code: "dc", label: "District of Columbia" },
  { code: "fl", label: "Florida" },
  { code: "ga", label: "Georgia" },
  { code: "hi", label: "Hawaii" },
  { code: "id", label: "Idaho" },
  { code: "il", label: "Illinois" },
  { code: "in", label: "Indiana" },
  { code: "ia", label: "Iowa" },
  { code: "ks", label: "Kansas" },
  { code: "ky", label: "Kentucky" },
  { code: "la", label: "Louisiana" },
  { code: "me", label: "Maine" },
  { code: "md", label: "Maryland" },
  { code: "ma", label: "Massachusetts" },
  { code: "mi", label: "Michigan" },
  { code: "mn", label: "Minnesota" },
  { code: "ms", label: "Mississippi" },
  { code: "mo", label: "Missouri" },
  { code: "mt", label: "Montana" },
  { code: "ne", label: "Nebraska" },
  { code: "nv", label: "Nevada" },
  { code: "nh", label: "New Hampshire" },
  { code: "nj", label: "New Jersey" },
  { code: "nm", label: "New Mexico" },
  { code: "ny", label: "New York" },
  { code: "nc", label: "North Carolina" },
  { code: "nd", label: "North Dakota" },
  { code: "oh", label: "Ohio" },
  { code: "ok", label: "Oklahoma" },
  { code: "or", label: "Oregon" },
  { code: "pa", label: "Pennsylvania" },
  { code: "ri", label: "Rhode Island" },
  { code: "sc", label: "South Carolina" },
  { code: "sd", label: "South Dakota" },
  { code: "tn", label: "Tennessee" },
  { code: "tx", label: "Texas" },
  { code: "ut", label: "Utah" },
  { code: "vt", label: "Vermont" },
  { code: "va", label: "Virginia" },
  { code: "wa", label: "Washington" },
  { code: "wv", label: "West Virginia" },
  { code: "wi", label: "Wisconsin" },
  { code: "wy", label: "Wyoming" },
];

const US: RegionOption = {
  code: "US",
  label: "United States",
  subRegions: [{ code: "national", label: "National (all US)" }, ...US_STATES],
};

const CA: RegionOption = {
  code: "CA",
  label: "Canada",
  subRegions: [
    { code: "national", label: "National (all Canada)" },
    { code: "ab", label: "Alberta" },
    { code: "bc", label: "British Columbia" },
    { code: "mb", label: "Manitoba" },
    { code: "nb", label: "New Brunswick" },
    { code: "nl", label: "Newfoundland and Labrador" },
    { code: "ns", label: "Nova Scotia" },
    { code: "nt", label: "Northwest Territories" },
    { code: "nu", label: "Nunavut" },
    { code: "on", label: "Ontario" },
    { code: "pe", label: "Prince Edward Island" },
    { code: "qc", label: "Quebec" },
    { code: "sk", label: "Saskatchewan" },
    { code: "yt", label: "Yukon" },
  ],
};

const country = (code: string, label: string): RegionOption => ({
  code,
  label,
  subRegions: [{ code: "national", label: "National" }],
});

/** Grouped regions for the submit dropdown. */
export const REGION_GROUPS: RegionGroup[] = [
  {
    label: "North America",
    regions: [US, CA, country("MX", "Mexico")],
  },
  {
    label: "Europe",
    regions: [
      {
        code: "UK",
        label: "United Kingdom",
        subRegions: [
          { code: "national", label: "National (all UK)" },
          { code: "england", label: "England" },
          { code: "scotland", label: "Scotland" },
          { code: "wales", label: "Wales" },
          { code: "northern-ireland", label: "Northern Ireland" },
        ],
      },
      country("IE", "Ireland"),
      country("DE", "Germany"),
      country("FR", "France"),
      country("ES", "Spain"),
      country("IT", "Italy"),
      country("NL", "Netherlands"),
      country("BE", "Belgium"),
      country("SE", "Sweden"),
      country("NO", "Norway"),
      country("DK", "Denmark"),
      country("FI", "Finland"),
      {
        code: "EU",
        label: "Europe (other)",
        subRegions: [{ code: "national", label: "National / unspecified" }],
      },
    ],
  },
  {
    label: "Asia-Pacific",
    regions: [
      {
        code: "AU",
        label: "Australia",
        subRegions: [
          { code: "national", label: "National (all Australia)" },
          { code: "act", label: "Australian Capital Territory" },
          { code: "nsw", label: "New South Wales" },
          { code: "nt", label: "Northern Territory" },
          { code: "qld", label: "Queensland" },
          { code: "sa", label: "South Australia" },
          { code: "tas", label: "Tasmania" },
          { code: "vic", label: "Victoria" },
          { code: "wa", label: "Western Australia" },
        ],
      },
      country("NZ", "New Zealand"),
      country("JP", "Japan"),
      country("KR", "South Korea"),
      country("CN", "China"),
      country("IN", "India"),
    ],
  },
  {
    label: "Latin America",
    regions: [
      country("BR", "Brazil"),
      {
        code: "LATAM",
        label: "Latin America (other)",
        subRegions: [{ code: "national", label: "National / unspecified" }],
      },
    ],
  },
  {
    label: "Other",
    regions: [
      {
        code: "OTHER",
        label: "Other",
        subRegions: [{ code: "custom", label: "Custom (enter below)" }],
      },
    ],
  },
];

export const REGION_OPTIONS: RegionOption[] = REGION_GROUPS.flatMap((g) => g.regions);

export function findRegion(code: string): RegionOption | undefined {
  return REGION_OPTIONS.find((r) => r.code === code);
}

/** Whether this region shows a sub-region dropdown (more than national-only). */
export function regionHasSubRegionPicker(regionCode?: string): boolean {
  if (!regionCode) return false;
  const def = findRegion(regionCode);
  if (!def) return false;
  if (regionCode === "OTHER") return true;
  return def.subRegions.length > 1;
}

/** Label for the sub-region field based on parent region. */
export function subRegionFieldLabel(regionCode?: string): string {
  switch (regionCode) {
    case "US":
      return "State / territory";
    case "CA":
      return "Province / territory";
    case "UK":
      return "Nation";
    case "AU":
      return "State / territory";
    default:
      return "Sub-region";
  }
}

export function formatRegionDisplay(region?: string | null, subRegion?: string | null): string | null {
  if (!region) return null;
  const regionDef = findRegion(region);
  const regionLabel = regionDef?.label ?? region;
  if (!subRegion) return regionLabel;
  const subDef = regionDef?.subRegions.find((s) => s.code === subRegion);
  const subLabel = subDef?.label ?? subRegion;
  if (subLabel.toLowerCase().includes("national") || subRegion === "national") {
    return regionLabel;
  }
  return `${regionLabel} · ${subLabel}`;
}
