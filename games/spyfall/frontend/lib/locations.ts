// Mirrors app/games/spyfall/locations.py on the backend. Only key +
// displayName are needed client-side — a player's own role text within a
// location arrives via the `role_assigned` event, so the per-location role
// lists don't need to be duplicated here.

export interface LocationInfo {
  key: string;
  displayName: string;
}

export const LOCATION_CATALOG: LocationInfo[] = [
  { key: "airplane", displayName: "Airplane" },
  { key: "bank", displayName: "Bank" },
  { key: "beach", displayName: "Beach" },
  { key: "casino", displayName: "Casino" },
  { key: "cathedral", displayName: "Cathedral" },
  { key: "circus_tent", displayName: "Circus Tent" },
  { key: "corporate_party", displayName: "Corporate Party" },
  { key: "crusader_army", displayName: "Crusader Army" },
  { key: "day_spa", displayName: "Day Spa" },
  { key: "embassy", displayName: "Embassy" },
  { key: "hospital", displayName: "Hospital" },
  { key: "hotel", displayName: "Hotel" },
  { key: "military_base", displayName: "Military Base" },
  { key: "movie_studio", displayName: "Movie Studio" },
  { key: "ocean_liner", displayName: "Ocean Liner" },
  { key: "passenger_train", displayName: "Passenger Train" },
  { key: "pirate_ship", displayName: "Pirate Ship" },
  { key: "polar_station", displayName: "Polar Station" },
  { key: "police_station", displayName: "Police Station" },
  { key: "restaurant", displayName: "Restaurant" },
  { key: "school", displayName: "School" },
  { key: "service_station", displayName: "Service Station" },
  { key: "space_station", displayName: "Space Station" },
  { key: "submarine", displayName: "Submarine" },
  { key: "supermarket", displayName: "Supermarket" },
  { key: "theater", displayName: "Theater" },
  { key: "university", displayName: "University" },
  { key: "amusement_park", displayName: "Amusement Park" },
];

export const LOCATION_BY_KEY: Map<string, LocationInfo> = new Map(
  LOCATION_CATALOG.map((location) => [location.key, location]),
);

export function locationDisplayName(key: string): string {
  return LOCATION_BY_KEY.get(key)?.displayName ?? key;
}
