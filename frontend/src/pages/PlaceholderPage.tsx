type PlaceholderPageProps = {
  title: string;
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="dashboard-placeholder">
      <h2>{title}</h2>
      <p>Dieser Bereich wird in einem folgenden Frontend-Schritt umgesetzt.</p>
    </section>
  );
}
