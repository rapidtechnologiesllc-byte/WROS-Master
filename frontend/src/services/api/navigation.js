// The user's menu, built by the backend from the permission catalogue (GET /hr/me/navigation):
// groups of {key, label, icon, route}, already filtered by the role template. The sidebar and the
// "Report an Issue" screen list both read it, so no screen list is hardcoded in the client.
import { apiRequest } from "./client";

let pending = null;

const parse = (result) => {
  const navData = result?.data?.data;
  if (!navData || !Array.isArray(navData.groups)) {
    throw new Error("Navigation response is missing its groups");
  }
  return navData.groups.map((group) => {
    if (!Array.isArray(group.items)) {
      throw new Error(`Navigation group "${group.label}" is missing its items`);
    }
    group.items.forEach((item) => {
      if (!item.route) throw new Error(`Navigation item "${item.key}" has no route`);
    });
    return group;
  });
};

/** The menu groups; one request per page load, shared by every caller. A failure is not cached. */
export const getNavigationGroups = () => {
  if (!pending) {
    pending = apiRequest("/hr/me/navigation", { method: "GET" })
      .then(parse)
      .catch((err) => {
        pending = null;
        throw err;
      });
  }
  return pending;
};

/** Distinct screen labels the user can reach, sorted. */
export const getScreenLabels = async () => {
  const groups = await getNavigationGroups();
  return Array.from(new Set(groups.flatMap((g) => g.items.map((item) => item.label)))).sort((a, b) =>
    a.localeCompare(b),
  );
};
