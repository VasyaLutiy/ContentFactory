"use client";

import { useMemo } from "react";

export type ApprovalState = "pending" | "approved" | "rejected" | "expired";

export type ApprovalCardModel = {
  id: string;
  title: string;
  action: string;
  state: ApprovalState;
  requestedBy: string;
  updatedAt: string;
  note: string;
};

export function useApprovalCards(cards?: ApprovalCardModel[]) {
  const approvalCards = useMemo(() => cards ?? [], [cards]);
  return { approvalCards };
}
