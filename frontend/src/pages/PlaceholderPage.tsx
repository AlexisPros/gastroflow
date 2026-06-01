type PlaceholderPageProps = {
  title: string;
  description: string;
};

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="page-stack">
      <div>
        <span className="eyebrow">Module</span>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      <div className="module-placeholder">
        <strong>Ready for implementation</strong>
        <p>
          This route is connected to the app shell, auth guard and role access.
        </p>
      </div>
    </section>
  );
}
