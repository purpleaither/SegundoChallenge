"use client";

import { useEffect } from "react";
import Script from "next/script";

// The official launcher lives in a shadow root, so page styles do not reach it.
export default function VLibrasWidget() {
  useEffect(() => {
    function styleLauncher() {
      const shadow = document.getElementById(
        "vlibras-access-wrapper",
      )?.shadowRoot;
      if (!shadow) return;
      let style = shadow.querySelector<HTMLStyleElement>("#guia-vlibras-style");
      if (!style) {
        style = document.createElement("style");
        style.id = "guia-vlibras-style";
        shadow.appendChild(style);
      }
      const contrast = document.documentElement.dataset.highContrast === "true";
      style.textContent = `
        #vlibras-access { width: 48px; height: 48px; top: calc(50vh - 24px); }
        #vlibras-access:hover, #vlibras-access:has(#vlibras-button:focus-visible) { width: 208px; }
        #vlibras-button, #vlibras-popup { height: 48px; border-radius: 10px; }
        #vlibras-button { width: 48px; box-sizing: border-box; border: 2px solid ${contrast ? "#ffed00" : "#fff"}; background: ${contrast ? "#000" : "#1351b4"}; }
        #vlibras-button > img { width: 100%; height: 100%; ${contrast ? "opacity: 0;" : ""} }
        ${contrast ? `#vlibras-button::after { content: ''; position: absolute; inset: 2px; background: #ffed00; mask: url('/vlibras-symbol.svg') center / contain no-repeat; }` : ""}
      `;
    }
    const launcherObserver = new MutationObserver(styleLauncher);
    launcherObserver.observe(document.body, { childList: true });
    const preferenceObserver = new MutationObserver(styleLauncher);
    preferenceObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-high-contrast"],
    });
    styleLauncher();
    return () => {
      launcherObserver.disconnect();
      preferenceObserver.disconnect();
    };
  }, []);

  return (
    <Script
      id="vlibras-widget"
      src="https://vlibras.gov.br/app/vlibras-plugin.js"
      strategy="afterInteractive"
    />
  );
}
