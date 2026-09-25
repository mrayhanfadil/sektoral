import logoSource from "../../../app/assets/brand/sectoral-logo.svg?raw";
import flowSource from "../../../app/assets/brand/research-flow.svg?raw";

// Inlined so the wordmark and diagram text use the embedded Roboto face.
const LOGO = logoSource.replace("Roboto, Arial, sans-serif", "Roboto, sans-serif");

export function Logo({ className = "h-[30px]" }: { className?: string }) {
  return <span className={`logo block [&>svg]:h-full [&>svg]:w-auto ${className}`} dangerouslySetInnerHTML={{ __html: LOGO }} />;
}

/** On phones the five-stage diagram keeps a readable size and scrolls sideways. */
export function ResearchFlow() {
  return (
    <div role="region" aria-label="Diagram alur riset" tabIndex={0} className="overflow-x-auto">
      <div className="svg-block mx-auto max-w-[1060px] max-md:w-[860px]" dangerouslySetInnerHTML={{ __html: flowSource }} />
    </div>
  );
}
