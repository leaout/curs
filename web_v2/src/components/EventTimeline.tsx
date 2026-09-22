import type { AgentEvent } from "../types";

interface EventTimelineProps {
  events: AgentEvent[];
}

const eventIcon: Record<AgentEvent["type"], string> = {
  signal: "⌁",
  context: "◇",
  model: "✦",
  risk: "✓",
  order: "↗",
  system: "•",
};

export function EventTimeline({ events }: EventTimelineProps) {
  return (
    <section className="timeline panel-edge">
      <div className="timeline-heading">
        <div><p className="eyebrow">LATEST RUN</p><h3>决策链</h3></div>
        <div className="run-meta">{events.length ? <><span className="live-pulse" /> 实时事件流</> : "等待首个策略评估"}</div>
      </div>
      <div className="timeline-track">
        {!events.length && <p className="timeline-empty">产生信号后，这里会显示上下文、模型、风控与订单决策链。</p>}
        {events.map((event, index) => (
          <div className={`timeline-event ${event.state}`} key={event.id}>
            {index < events.length - 1 && <span className="timeline-connector" />}
            <div className="event-icon">{eventIcon[event.type]}</div>
            <div className="event-time">{event.timestamp}</div>
            <strong>{event.title}</strong>
            <p>{event.detail}</p>
            {event.durationMs !== undefined && <small>{event.durationMs.toLocaleString()} ms</small>}
          </div>
        ))}
      </div>
    </section>
  );
}
