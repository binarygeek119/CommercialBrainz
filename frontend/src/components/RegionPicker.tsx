import {
  REGION_GROUPS,
  findRegion,
  regionHasSubRegionPicker,
  subRegionFieldLabel,
} from "../data/regions";

export interface RegionSelection {
  region?: string;
  sub_region?: string;
  sub_region_custom?: string;
}

interface RegionSelectProps {
  value: RegionSelection;
  onChange: (value: RegionSelection) => void;
}

export function RegionSelect({ value, onChange }: RegionSelectProps) {
  const handleRegionChange = (region: string) => {
    onChange({
      region: region || undefined,
      sub_region: undefined,
      sub_region_custom: undefined,
    });
  };

  return (
    <select
      id="region-select"
      value={value.region ?? ""}
      onChange={(e) => handleRegionChange(e.target.value)}
    >
      <option value="">Select region…</option>
      {REGION_GROUPS.map((group) => (
        <optgroup key={group.label} label={group.label}>
          {group.regions.map((r) => (
            <option key={r.code} value={r.code}>
              {r.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

interface SubRegionSelectProps {
  value: RegionSelection;
  onChange: (value: RegionSelection) => void;
}

export function SubRegionSelect({ value, onChange }: SubRegionSelectProps) {
  const regionDef = value.region ? findRegion(value.region) : undefined;
  const subRegions = regionDef?.subRegions ?? [];
  const showCustomSub =
    value.region === "OTHER" || value.sub_region === "custom";

  if (!value.region || !regionHasSubRegionPicker(value.region)) {
    return null;
  }

  const handleSubRegionChange = (sub_region: string) => {
    onChange({
      ...value,
      sub_region: sub_region || undefined,
      sub_region_custom: sub_region === "custom" ? value.sub_region_custom : undefined,
    });
  };

  const nationalOption = subRegions.find((s) => s.code === "national");
  const customOption = subRegions.find((s) => s.code === "custom");
  const localOptions = subRegions.filter(
    (s) => s.code !== "national" && s.code !== "custom"
  );

  return (
    <>
      {value.region !== "OTHER" && (
        <select
          key={value.region}
          id="sub-region-select"
          value={value.sub_region ?? ""}
          onChange={(e) => handleSubRegionChange(e.target.value)}
        >
          <option value="">
            Select {subRegionFieldLabel(value.region).toLowerCase()}…
          </option>
          {nationalOption && (
            <option value={nationalOption.code}>{nationalOption.label}</option>
          )}
          {localOptions.length > 0 && value.region === "US" ? (
            <optgroup label="States">
              {localOptions.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.label}
                </option>
              ))}
            </optgroup>
          ) : (
            localOptions.map((s) => (
              <option key={s.code} value={s.code}>
                {s.label}
              </option>
            ))
          )}
          {customOption && (
            <option value={customOption.code}>{customOption.label}</option>
          )}
        </select>
      )}

      {showCustomSub && (
        <input
          id="sub-region-custom"
          type="text"
          value={value.sub_region_custom ?? ""}
          onChange={(e) =>
            onChange({ ...value, sub_region_custom: e.target.value || undefined })
          }
          placeholder="e.g. Nordic, Iberia, Pacific Northwest"
          style={{ marginTop: "0.75rem" }}
        />
      )}
    </>
  );
}

export default function RegionPicker(props: RegionSelectProps) {
  return (
    <>
      <RegionSelect {...props} />
      <SubRegionSelect {...props} />
    </>
  );
}

export { regionHasSubRegionPicker, subRegionFieldLabel };

/** Resolve selection to API payload values. */
export function regionSelectionToPayload(selection: RegionSelection): {
  region?: string;
  sub_region?: string;
} {
  if (!selection.region) return {};
  let sub = selection.sub_region;
  if (sub === "custom" && selection.sub_region_custom?.trim()) {
    sub = selection.sub_region_custom.trim().toLowerCase().replace(/\s+/g, "-");
  }
  if (!sub || sub === "national") {
    return { region: selection.region };
  }
  return { region: selection.region, sub_region: sub };
}
