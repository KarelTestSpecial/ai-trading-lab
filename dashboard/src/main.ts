import "./style.css";

interface OrderRecord {
  symbol: string;
  side: string;
  qty: number;
  notional: number;
  order_id?: string;
  veto_reason?: string;
}

interface Decision {
  event: string;
  as_of: string;
  dry_run?: boolean;
  strategy?: string;
  account_equity: number;
  cash?: number;
  drawdown_pct?: number;
  target_weights?: Record<string, number>;
  submitted?: OrderRecord[];
  vetoed?: OrderRecord[];
}

const SVG_NS = "http://www.w3.org/2000/svg";
const app = document.querySelector<HTMLDivElement>("#app")!;

function elem(tag: string, className?: string, text?: string): HTMLElement {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgElem(tag: string, attrs: Record<string, string>): SVGElement {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function pct(value: number | undefined): string {
  return value === undefined || Number.isNaN(value) ? "n/a" : `${(value * 100).toFixed(2)}%`;
}

function equityChart(values: number[]): SVGElement {
  const width = 800;
  const height = 240;
  const pad = 36;
  const svg = svgElem("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart" });
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = values.length > 1 ? (width - 2 * pad) / (values.length - 1) : 0;
  const points = values.map((value, i) => {
    const x = pad + i * stepX;
    const y = height - pad - ((value - min) / span) * (height - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  svg.append(
    svgElem("line", { x1: `${pad}`, y1: `${height - pad}`, x2: `${width - pad}`, y2: `${height - pad}`, class: "axis" }),
  );
  svg.append(svgElem("polyline", { points: points.join(" "), class: "line" }));
  const highLabel = svgElem("text", { x: `${pad}`, y: `${pad - 8}`, class: "axis-label" });
  highLabel.textContent = max.toFixed(0);
  const lowLabel = svgElem("text", { x: `${pad}`, y: `${height - pad + 18}`, class: "axis-label" });
  lowLabel.textContent = min.toFixed(0);
  svg.append(highLabel, lowLabel);
  return svg;
}

function statCard(label: string, value: string): HTMLElement {
  const card = elem("div", "card");
  card.append(elem("div", "card-label", label), elem("div", "card-value", value));
  return card;
}

function ordersTable(orders: OrderRecord[], withVeto = false): HTMLElement {
  const table = elem("table");
  const header = elem("tr");
  for (const heading of withVeto ? ["symbol", "side", "qty", "notional", "reason"] : ["symbol", "side", "qty", "notional"]) {
    header.append(elem("th", undefined, heading));
  }
  table.append(header);
  for (const order of orders) {
    const row = elem("tr");
    row.append(
      elem("td", undefined, order.symbol),
      elem("td", undefined, order.side),
      elem("td", undefined, String(order.qty)),
      elem("td", undefined, order.notional.toFixed(2)),
    );
    if (withVeto) row.append(elem("td", "veto", order.veto_reason ?? ""));
    table.append(row);
  }
  return table;
}

function render(decisions: Decision[]): void {
  app.replaceChildren();

  const header = elem("header");
  header.append(
    elem("h1", undefined, "Cadence"),
    elem(
      "p",
      "subtitle",
      "Public paper-trading track record (US equities, daily). Repo: ai-trading-lab.",
    ),
  );
  app.append(header);

  const disclaimer = elem(
    "div",
    "disclaimer",
    "Simulation only — no real money, not investment advice. Past performance is not indicative of future results. " +
      "Data is the append-only journal committed to the repository; any later edit is visible in git history.",
  );
  app.append(disclaimer);

  if (decisions.length === 0) {
    const empty = elem("div", "empty");
    empty.append(
      elem("h2", undefined, "No decisions yet"),
      elem(
        "p",
        undefined,
        "The daily paper loop has not recorded a decision yet. Once it runs, the equity curve, positions and " +
          "decision log appear here automatically from journal/decisions.jsonl.",
      ),
    );
    app.append(empty);
    return;
  }

  const equity = decisions.map((decision) => decision.account_equity);
  const totalReturn = equity[equity.length - 1] / equity[0] - 1;
  const maxDrawdown = Math.min(...decisions.map((decision) => decision.drawdown_pct ?? 0));
  const latest = decisions[decisions.length - 1];

  const stats = elem("section", "cards");
  stats.append(
    statCard("Decisions", String(decisions.length)),
    statCard("Equity", latest.account_equity.toFixed(2)),
    statCard("Total return", pct(totalReturn)),
    statCard("Max drawdown", pct(maxDrawdown)),
  );
  app.append(stats);

  const chartSection = elem("section");
  chartSection.append(elem("h2", undefined, "Equity curve"), equityChart(equity));
  app.append(chartSection);

  const latestSection = elem("section");
  latestSection.append(elem("h2", undefined, `Latest decision — ${latest.as_of}`));
  const weights = latest.target_weights ?? {};
  const weightsList = elem("p", "weights");
  const entries = Object.entries(weights);
  weightsList.textContent =
    entries.length === 0
      ? "Target: all cash."
      : "Target: " + entries.map(([symbol, weight]) => `${symbol} ${pct(weight)}`).join(", ");
  latestSection.append(weightsList);
  if ((latest.submitted ?? []).length > 0) {
    latestSection.append(elem("h3", undefined, "Submitted orders"), ordersTable(latest.submitted ?? []));
  }
  if ((latest.vetoed ?? []).length > 0) {
    latestSection.append(elem("h3", undefined, "Risk vetoes"), ordersTable(latest.vetoed ?? [], true));
  }
  app.append(latestSection);

  const logSection = elem("section");
  logSection.append(elem("h2", undefined, "Decision log"));
  const logTable = elem("table");
  const logHeader = elem("tr");
  for (const heading of ["date", "equity", "drawdown", "submitted", "vetoed"]) {
    logHeader.append(elem("th", undefined, heading));
  }
  logTable.append(logHeader);
  for (const decision of [...decisions].reverse()) {
    const row = elem("tr");
    row.append(
      elem("td", undefined, decision.as_of),
      elem("td", undefined, decision.account_equity.toFixed(2)),
      elem("td", undefined, pct(decision.drawdown_pct ?? 0)),
      elem("td", undefined, String((decision.submitted ?? []).length)),
      elem("td", undefined, String((decision.vetoed ?? []).length)),
    );
    logTable.append(row);
  }
  logSection.append(logTable);
  app.append(logSection);
}

async function main(): Promise<void> {
  const url = new URL("decisions.jsonl", document.baseURI);
  let decisions: Decision[] = [];
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (response.ok) {
      const text = await response.text();
      decisions = text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => JSON.parse(line) as Decision)
        .filter((record) => record.event === "paper_decision");
    }
  } catch {
    decisions = [];
  }
  render(decisions);
}

void main();
