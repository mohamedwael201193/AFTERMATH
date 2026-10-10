"use client";

import * as React from "react";

/**
 * Media-query hook for the decision-detail surface split:
 * below xl the record opens in a drawer; at xl+ it opens in the
 * right-hand panel. Prevents double-mounting charts in hidden containers.
 */
export function useBelowXl(): boolean {
  const [below, setBelow] = React.useState<boolean>(true);

  React.useEffect(() => {
    const mql = window.matchMedia("(max-width: 1279px)");
    const onChange = () => setBelow(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return below;
}
