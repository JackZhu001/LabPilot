import { useI18n } from "@/i18n";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/ui/primitives";

export default function SettingsPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader
        title={t("Settings")}
        description={t("Frontend preferences. Research and execution configuration is managed by the LabPilot CLI and its persisted state.")}
      />
      <Panel title={t("Display")}>
        <p className="text-[13px] leading-relaxed text-muted">
          {t("Switch between graphite and light themes using the sun or moon button in the top bar. Your preference stays on this device. Motion follows your system’s reduced-motion setting; the dashboard’s 3D model also has a pause control.")}</p>
      <p className="mt-4 text-sm leading-relaxed text-muted">{t("Use 中文 / EN in the top bar to switch languages. Use the animation button to pause all motion. Preferences are saved on this device. Research content and exported snapshots stay in their original language.")}</p>
      </Panel>
    </>
  );
}
