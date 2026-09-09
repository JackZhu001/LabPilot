import { Link } from "react-router-dom";
import { EmptyState } from "@/components/ui/primitives";

export default function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="The page you requested does not exist in this control plane."
      action={
        <Link to="/dashboard" className="text-[13px] font-medium text-accent-ink hover:underline">
          Back to dashboard
        </Link>
      }
    />
  );
}
