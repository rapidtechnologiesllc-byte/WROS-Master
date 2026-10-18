import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * The active tab of a tabbed screen, kept in the URL (?tab=<key>) so old routes can redirect
 * straight to a tab and a tab can be bookmarked. Unknown or missing values fall back to the
 * first key in `keys`.
 */
export default function useTabParam(keys) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get("tab");
  const active = keys.includes(requested) ? requested : keys[0];
  const setActive = useCallback(
    (key) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", key);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );
  return [active, setActive];
}
