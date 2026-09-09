import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/ui/primitives";

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="Frontend preferences. Research and execution configuration is managed by the LabPilot CLI and its persisted state."
      />
      <Panel title="Display">
        <p className="text-[13px] leading-relaxed text-muted">
          LabPilot ships a single calibrated light theme suited to dense technical work. Theme
          selection and layout density options will arrive with backend-driven configuration.
        </p>
      </Panel>
    </>
  );
}
