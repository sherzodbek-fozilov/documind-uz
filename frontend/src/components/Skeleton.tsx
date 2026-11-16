/** Placeholder lines shown while content loads; hidden from assistive technology (the
 * surrounding element carries the status text). */
export function SkeletonLines({ widths }: { widths: readonly string[] }) {
  return (
    <div className="skeleton-lines" aria-hidden="true">
      {widths.map((w, i) => <span key={i} className="skeleton" style={{ width: w }} />)}
    </div>
  );
}
