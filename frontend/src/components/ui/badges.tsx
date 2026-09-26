import { useI18n } from "@/i18n";
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
  const { t } = useI18n();
  switch (status) {
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          {t("RUNNING")}</Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="warning" icon={icon(Pause)}>
          {t("PAUSED")}</Badge>
      );
    case "COMPLETED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("COMPLETED")}</Badge>
      );
    case "BLOCKED":
      return (
        <Badge variant="warning" icon={icon(Pause)}>
          {t("BLOCKED")}</Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("FAILED")}</Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(CircleDot)}>
          {t("READY")}</Badge>
      );
  }
}

export function ExperimentStatusBadge({ status }: { status: ExperimentStatus }) {
  const { t } = useI18n();
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("SUCCEEDED")}</Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("FAILED")}</Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          {t("RUNNING")}</Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(Circle)}>
          {t("PENDING")}</Badge>
      );
  }
}

export function TrialStatusBadge({ status }: { status: TrialStatus }) {
  const { t } = useI18n();
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("SUCCEEDED")}</Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("FAILED")}</Badge>
      );
    case "PRUNED":
      return (
        <Badge variant="neutral" icon={icon(Scissors)}>
          {t("PRUNED")}</Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="accent" icon={icon(Play)}>
          {t("RUNNING")}</Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(Circle)}>
          {t("PENDING")}</Badge>
      );
  }
}

export function StudyStatusBadge({ status }: { status: StudyStatus }) {
  const { t } = useI18n();
  switch (status) {
    case "SUCCEEDED":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("SUCCEEDED")}</Badge>
      );
    case "FAILED":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("FAILED")}</Badge>
      );
    default:
      return (
        <Badge variant="accent" icon={icon(Play)}>
          {t("RUNNING")}</Badge>
      );
  }
}

export function DecisionBadge({ decision }: { decision: ResearchDecision }) {
  const { t } = useI18n();
  switch (decision) {
    case "KEEP":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("KEEP")}</Badge>
      );
    case "REJECT":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("REJECT")}</Badge>
      );
    case "REPLAN":
      return (
        <Badge variant="warning" icon={icon(RotateCcw)}>
          {t("REPLAN")}</Badge>
      );
  }
}

export function DecisionPendingBadge() {
  const { t } = useI18n();
  return (
    <Badge variant="outline" icon={icon(CircleDot)}>
      {t("PENDING")}</Badge>
  );
}

export function PurposeBadge({ purpose }: { purpose: ExperimentPurpose }) {
  const { t } = useI18n();
  return purpose === "BASELINE" ? (
    <Badge variant="outline" icon={icon(CircleDot)}>
      {t("BASELINE")}</Badge>
  ) : (
    <Badge variant="accent" icon={icon(Play)}>
      {t("CANDIDATE")}</Badge>
  );
}

export function RelationBadge({ relation }: { relation: EvidenceRelation }) {
  const { t } = useI18n();
  switch (relation) {
    case "SUPPORT":
      return (
        <Badge variant="success" icon={icon(Check)}>
          {t("SUPPORT")}</Badge>
      );
    case "CONTRADICT":
      return (
        <Badge variant="danger" icon={icon(X)}>
          {t("CONTRADICT")}</Badge>
      );
    default:
      return (
        <Badge variant="neutral" icon={icon(CircleDot)}>
          {t("NEUTRAL")}</Badge>
      );
  }
}
