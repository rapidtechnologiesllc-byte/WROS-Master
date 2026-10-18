import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * The active tab of a tabbed screen, kept in the URL (?tab=<key>, or ?<param>=<key>) so old
 * routes can redirect straight to a tab and a tab can be bookmarked. Unknown or missing values
 * fall back to the first key in `keys`. Merged screens use param "view" so a screen inside one
 * can keep its own ?tab.
 */
export default function useTabParam(keys, param = "tab") {
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get(param);
  const active = keys.includes(requested) ? requested : keys[0];
  const setActive = useCallback(
    (key) => {
      const next = new URLSearchParams(searchParams);
      next.set(param, key);
      setSearchParams(next, { replace: true });
    },
    [param, searchParams, setSearchParams],
  );
  return [active, setActive];
}
