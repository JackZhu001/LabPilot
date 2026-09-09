import {
  Check,
  Circle,
  CircleDot,
  Pause,
  Play,
  RotateCcw,
  Scissors,
  X,
} from "lucide-react";
import type {
  EvidenceRelation,
  ExperimentPurpose,
  ExperimentStatus,
  ResearchDecision,
  RunStatus,
  StudyStatus,
  TrialStatus,
} from "@/types/domain";
import { Badge } from "@/components/ui/primitives";

const icon = (El: typeof Check, size = "size-3") => (
  <El className={size} strokeWidth={2} aria-hidden="true" />
);

/* Status — never color alone; every badge carries a distinct glyph. */

export function RunStatusBadge({ status }: { status: RunStatus }) {
  switch (status) {
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          RUNNING
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="warning" icon={icon(Pause)}>
          PAUSED
        </Badge>
      );
    case "COMPLETED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          COMPLETED
        </Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(CircleDot)}>
          READY
        </Badge>
      );
  }
}

export function ExperimentStatusBadge({ status }: { status: ExperimentStatus }) {
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          SUCCEEDED
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          FAILED
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          RUNNING
        </Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(Circle)}>
          PENDING
        </Badge>
      );
  }
}

export function TrialStatusBadge({ status }: { status: TrialStatus }) {
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          SUCCEEDED
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          FAILED
        </Badge>
      );
    case "PRUNED":
      return (
        <Badge variant="neutral" icon={icon(Scissors)}>
          PRUNED
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          RUNNING
        </Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(Circle)}>
          PENDING
        </Badge>
      );
  }
}

export function StudyStatusBadge({ status }: { status: StudyStatus }) {
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          SUCCEEDED
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          FAILED
        </Badge>
      );
    default:
      return (
        <Badge variant="accent" icon={icon(Play)}>
          RUNNING
        </Badge>
      );
  }
}

export function DecisionBadge({ decision }: { decision: ResearchDecision }) {
  switch (decision) {
    case "KEEP":
      return (
        <Badge variant="success" icon={icon(Check)}>
          KEEP
        </Badge>
      );
    case "REJECT":
      return (
        <Badge variant="danger" icon={icon(X)}>
          REJECT
        </Badge>
      );
    case "REPLAN":
      return (
        <Badge variant="warning" icon={icon(RotateCcw)}>
          REPLAN
        </Badge>
      );
  }
}

export function DecisionPendingBadge() {
  return (
    <Badge variant="outline" icon={icon(CircleDot)}>
      PENDING
    </Badge>
  );
}

export function PurposeBadge({ purpose }: { purpose: ExperimentPurpose }) {
  return purpose === "BASELINE" ? (
    <Badge variant="outline" icon={icon(CircleDot)}>
      BASELINE
    </Badge>
  ) : (
    <Badge variant="accent" icon={icon(Play)}>
      CANDIDATE
    </Badge>
  );
}

export function RelationBadge({ relation }: { relation: EvidenceRelation }) {
  switch (relation) {
    case "SUPPORT":
      return (
        <Badge variant="success" icon={icon(Check)}>
          SUPPORT
        </Badge>
      );
    case "CONTRADICT":
      return (
        <Badge variant="danger" icon={icon(X)}>
          CONTRADICT
        </Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(CircleDot)}>
          NEUTRAL
        </Badge>
      );
  }
}

