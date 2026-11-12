export default function Loading() {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" /> Chargement des prix…
    </div>
  );
}
