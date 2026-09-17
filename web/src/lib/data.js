import { useEffect, useState } from "react";

const base = import.meta.env.BASE_URL;
const cache = new Map();

function load(name) {
  if (!cache.has(name)) {
    cache.set(
      name,
      fetch(`${base}data/${name}`).then((response) => {
        if (!response.ok) throw new Error(`${name} could not be loaded (${response.status})`);
        return response.json();
      }),
    );
  }
  return cache.get(name);
}

/** Load one exported JSON file. Values are never invented while it is missing: `data` stays null. */
export function useData(name) {
  const [state, setState] = useState({ data: null, error: null });
  useEffect(() => {
    if (!name) return undefined;
    let live = true;
    load(name)
      .then((data) => live && setState({ data, error: null }))
      .catch((error) => live && setState({ data: null, error }));
    return () => {
      live = false;
    };
  }, [name]);
  return state;
}

/** Names of the data files the exporter wrote; sections whose results are still computing are absent. */
export function useAvailable() {
  const { data } = useData("manifest.json");
  return data ? new Set(data.available) : null;
}

export const repoUrl = "https://github.com/dhruvin-sarkar/fault-lines";
export const blobUrl = (path) => `${repoUrl}/blob/main/${path}`;

/** The technical report, published beside the site by the build. */
export const reportUrl = `${base}report.pdf`;
