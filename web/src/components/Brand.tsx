import logoSource from "../../../app/assets/brand/sectoral-logo.svg?raw";
import flowSource from "../../../app/assets/brand/research-flow.svg?raw";

// Inlined so the wordmark and diagram text use the embedded Roboto face.
const LOGO = logoSource.replace("Roboto, Arial, sans-serif", "Roboto, sans-serif");

export function Logo({ className = "h-[30px]" }: { className?: string }) {
  return <span className={`block [&>svg]:h-full [&>svg]:w-auto ${className}`} dangerouslySetInnerHTML={{ __html: LOGO }} />;
}

export function ResearchFlow() {
  return <div className="svg-block mx-auto max-w-[1060px]" dangerouslySetInnerHTML={{ __html: flowSource }} />;
}
