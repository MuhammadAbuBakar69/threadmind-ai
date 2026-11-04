/**
 * Dashboard placeholder.
 *
 * The real surface (Phase 6) is three panels: factory health, machine condition, and open
 * investigations. Each number on screen must be traceable to a record — a dashboard that shows an
 * unattributed score teaches operators to distrust the system.
 */

const panels = [
  {
    title: "Factory health",
    body: "First-pass yield, defect rate, and open critical alerts for the selected factory.",
    requirement: "FR-049",
  },
  {
    title: "Machine condition",
    body: "Anomaly score, risk category, and the sensor evidence behind each — with model version.",
    requirement: "FR-050",
  },
  {
    title: "Investigations",
    body: "Ranked hypotheses with supporting and contradictory evidence, awaiting engineer review.",
    requirement: "FR-033",
  },
];

export default function Home() {
  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: "4rem 1.5rem" }}>
      <p style={{ letterSpacing: "0.18em", fontSize: 12, textTransform: "uppercase", opacity: 0.6 }}>
        ThreadMind AI
      </p>
      <h1 style={{ fontSize: "2.25rem", margin: "0.5rem 0 0.75rem" }}>
        Textile factory intelligence
      </h1>
      <p style={{ maxWidth: 620, lineHeight: 1.6, opacity: 0.75 }}>
        Decision support, not machine control. Every recommendation carries the evidence that
        produced it and stops for a human before it becomes an action.
      </p>

      <div
        style={{
          display: "grid",
          gap: "1rem",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          marginTop: "2.5rem",
        }}
      >
        {panels.map((panel) => (
          <section
            key={panel.title}
            style={{ border: "1px solid rgba(127,127,127,0.25)", borderRadius: 10, padding: "1.25rem" }}
          >
            <h2 style={{ fontSize: "1rem", margin: 0 }}>{panel.title}</h2>
            <p style={{ lineHeight: 1.55, fontSize: 14, opacity: 0.75 }}>{panel.body}</p>
            <code style={{ fontSize: 11, opacity: 0.5 }}>{panel.requirement}</code>
          </section>
        ))}
      </div>
    </main>
  );
}
