import { useI18n } from "@/i18n";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/ui/primitives";

export default function NotFoundPage() {
  const { t } = useI18n();
  return (
    <EmptyState
      title={t("Page not found")}
      description={t("The page you requested does not exist in this control plane.")}
      action={
        <Link to="/dashboard" className="text-[13px] font-medium text-accent-ink hover:underline">
          {t("Back to dashboard")}</Link>
      }
    />
  );
}
