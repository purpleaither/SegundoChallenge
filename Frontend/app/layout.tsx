import type { Metadata, Viewport } from "next";
import VLibrasWidget from "./components/vlibras-widget";
import AccessibilityTools from "./components/accessibility-tools";
import "./globals.css";

export const metadata: Metadata = {
  title: "GuIA Social | Benefícios sociais no DF",
  description:
    "Descubra benefícios sociais disponíveis no Distrito Federal com orientação simples, acolhedora e confiável.",
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#0c3f96",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>
        {children}
        <AccessibilityTools />
        <VLibrasWidget />
      </body>
    </html>
  );
}
