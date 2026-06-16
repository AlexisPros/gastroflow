type PlaceholderPageProps = {
  title: string;
  description: string;
};

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="page-stack">
      <div>
        <span className="eyebrow">Moduł</span>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      <div className="module-placeholder">
        <strong>Gotowe do wdrożenia</strong>
        <p>
          Ta trasa jest połączona ze szkieletem aplikacji, ochroną uwierzytelniania i dostępem do ról.
        </p>
      </div>
    </section>
  );
}
