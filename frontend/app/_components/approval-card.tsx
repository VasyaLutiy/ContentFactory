import type { ApprovalCardModel } from "./use-approval-cards";

const approvalStateMeta: Record<
  ApprovalCardModel["state"],
  { label: string; toneClass: string }
> = {
  pending: {
    label: "Pending",
    toneClass: "approval-pill pending",
  },
  approved: {
    label: "Approved",
    toneClass: "approval-pill approved",
  },
  rejected: {
    label: "Rejected",
    toneClass: "approval-pill rejected",
  },
  expired: {
    label: "Expired",
    toneClass: "approval-pill expired",
  },
};

export function ApprovalCard({ card }: { card: ApprovalCardModel }) {
  const stateMeta = approvalStateMeta[card.state];

  return (
    <article className="copilot-card approval-card" aria-label={`${stateMeta.label} approval`}>
      <div className="approval-card-head">
        <span>Approval</span>
        <strong className={stateMeta.toneClass}>{stateMeta.label}</strong>
      </div>
      <strong>{card.title}</strong>
      <p>{card.action}</p>
      <small>
        {card.requestedBy} · {card.updatedAt}
      </small>
      <p>{card.note}</p>
    </article>
  );
}
