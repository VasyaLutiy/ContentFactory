"use client";

import { FormEvent, useState } from "react";

type CopilotMessage = {
  id: string;
  role: "assistant" | "operator";
  time: string;
  text: string;
};

const initialMessages: CopilotMessage[] = [
  {
    id: "msg-1",
    role: "assistant",
    time: "14:02",
    text: "Queue drift detected on P1 jobs. I can reprioritize two renders after policy checks clear.",
  },
  {
    id: "msg-2",
    role: "operator",
    time: "14:03",
    text: "Keep Neon Relic first. Hold Arc Forge until caption-safe pass is confirmed.",
  },
  {
    id: "msg-3",
    role: "assistant",
    time: "14:04",
    text: "Acknowledged. I prepared a dry-run order change and a policy checklist delta.",
  },
];

const eventCards = [
  {
    id: "evt-1",
    label: "Event",
    title: "Queue reorder proposed",
    detail: "2 jobs moved, no active render interruption.",
  },
  {
    id: "tool-1",
    label: "Tool",
    title: "policy.diff",
    detail: "No violations in first-frame text window.",
  },
  {
    id: "status-1",
    label: "Status",
    title: "Awaiting operator confirm",
    detail: "Approval required before outbound queue changes.",
  },
];

export function CopilotPanel() {
  const [messages, setMessages] = useState<CopilotMessage[]>(initialMessages);
  const [draft, setDraft] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) {
      return;
    }

    const time = new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date());
    const id = `${Date.now()}`;
    setMessages((current) => [
      ...current,
      {
        id: `operator-${id}`,
        role: "operator",
        time,
        text: content,
      },
      {
        id: `assistant-${id}`,
        role: "assistant",
        time,
        text: "Logged as an operator note. Backend execution will stay approval-gated.",
      },
    ]);
    setDraft("");
  }

  return (
    <aside className="copilot" aria-label="Copilot panel">
      <div className="copilot-head">
        <div>
          <h2>Copilot</h2>
          <p>Operator session</p>
        </div>
        <span className="badge muted">Review</span>
      </div>

      <div className="copilot-feed" aria-label="Chat messages">
        {messages.map((message) => (
          <article className={`chat-message ${message.role}`} key={message.id}>
            <div className="chat-meta">
              <strong>{message.role === "assistant" ? "Copilot" : "Operator"}</strong>
              <span>{message.time}</span>
            </div>
            <p>{message.text}</p>
          </article>
        ))}
      </div>

      <div className="copilot-cards" aria-label="Event and tool cards">
        {eventCards.map((card) => (
          <article className="copilot-card" key={card.id}>
            <span>{card.label}</span>
            <strong>{card.title}</strong>
            <p>{card.detail}</p>
          </article>
        ))}
      </div>

      <form className="copilot-input" onSubmit={handleSubmit}>
        <label htmlFor="copilot-prompt">Command</label>
        <textarea
          id="copilot-prompt"
          name="copilot-prompt"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about a job, artifact, caption, or queue action..."
          rows={3}
          value={draft}
        />
        <div className="copilot-actions">
          <small>Approval gates active</small>
          <button type="submit">Send</button>
        </div>
      </form>
    </aside>
  );
}
