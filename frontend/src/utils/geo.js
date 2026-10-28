// The offline country / state / city dataset (country-state-city). Countries (~0.1 MB) and states
// (~0.5 MB) load with the app; cities are 7.7 MB, so they load on first use only (their own chunk),
// never in the main bundle every page downloads. Import from here, never from the package root:
// "country-state-city" pulls all three.
import Country from "country-state-city/lib/country";
import State from "country-state-city/lib/state";

let cities = null;

// Resolves to the City module ({ getCitiesOfState, ... }); downloaded once, then cached.
export function loadCities() {
  if (!cities) {
    cities = import(/* webpackChunkName: "cities" */ "country-state-city/lib/city").then((module) => module.default);
  }
  return cities;
}

export { Country, State };
