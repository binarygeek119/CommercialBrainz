export interface SubmissionTermsSubsection {
  heading: string;
  bullets?: string[];
  paragraphs?: string[];
}

export interface SubmissionTermsSection {
  number?: number;
  heading: string;
  paragraphs?: string[];
  bullet_label?: string;
  bullets?: string[];
  subsections?: SubmissionTermsSubsection[];
}

export interface SubmissionTerms {
  version: number;
  title: string;
  intro: string;
  sections: SubmissionTermsSection[];
}

interface SubmissionTermsViewProps {
  terms: SubmissionTerms;
  compact?: boolean;
}

export default function SubmissionTermsView({ terms, compact = false }: SubmissionTermsViewProps) {
  return (
    <div className={compact ? "terms-view terms-view-compact" : "terms-view"}>
      <h2>{terms.title}</h2>
      <p className="muted">{terms.intro}</p>
      {terms.sections.map((section) => (
        <section key={section.number ?? section.heading} className="terms-section">
          <h3>
            {section.number != null ? `${section.number}. ` : ""}
            {section.heading}
          </h3>
          {section.paragraphs?.map((p) => (
            <p key={p} className="muted">
              {p}
            </p>
          ))}
          {section.subsections?.map((sub) => (
            <div key={sub.heading} className="terms-subsection">
              <h4>{sub.heading}</h4>
              {sub.paragraphs?.map((p) => (
                <p key={p} className="muted">
                  {p}
                </p>
              ))}
              {sub.bullets && sub.bullets.length > 0 && (
                <ul>
                  {sub.bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          {section.bullet_label && <p className="terms-bullet-label">{section.bullet_label}</p>}
          {section.bullets && section.bullets.length > 0 && (
            <ul>
              {section.bullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
