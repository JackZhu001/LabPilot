import { useI18n } from "@/i18n";
import { useRef, useState, type CSSProperties } from "react";
import { Pause, Play } from "lucide-react";

/** A CSS 3D model of the research loop, not a live progress visualization. */
export function ResearchCore() {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  return (
    <div className="core-scene" data-paused={paused} ref={ref}
      onPointerMove={(event) => {
        if (paused || document.documentElement.dataset.motion === "off" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        ref.current?.style.setProperty("--tilt-x", `${(event.clientY - bounds.top - bounds.height / 2) / -22}deg`);
        ref.current?.style.setProperty("--tilt-y", `${(event.clientX - bounds.left - bounds.width / 2) / 22}deg`);
      }}
      onPointerLeave={() => {
        ref.current?.style.setProperty("--tilt-x", "0deg");
        ref.current?.style.setProperty("--tilt-y", "0deg");
      }}>
      <div className="core-grid" aria-hidden="true" />
      <div className="core-particles" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <i key={i} style={{ "--i": i } as CSSProperties} />)}</div>
      <div className="core-perspective" aria-hidden="true">
        <div className="core-tilt">
          <div className="core-orbit orbit-one" />
          <div className="core-orbit orbit-two" />
          <div className="core-orbit orbit-three" />
          <div className="core-globe">
            {Array.from({ length: 18 }, (_, index) => (
              <span className="core-meridian" key={index} style={{ "--angle": `${index * 10}deg` } as CSSProperties} />
            ))}
            <span className="core-equator" />
            <span className="core-equator equator-two" />
          </div>
          <div className="core-light" />
        </div>
      </div>
      <div className="core-caption"><span>{t("Research in motion")}</span><span className="font-mono text-[10px]">{t("Interactive 3D model")}</span></div>
      <button className="core-toggle" type="button" onClick={() => setPaused(!paused)}
        aria-label={paused ? t("Resume 3D motion") : t("Pause 3D motion")} aria-pressed={paused}>
        {paused ? <Play size={14} /> : <Pause size={14} />}
      </button>
    </div>
  );
}
