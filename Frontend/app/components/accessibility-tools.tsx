"use client";

import { useEffect, useRef, useState } from "react";
import { Minus, Moon, Plus, RotateCcw, Sun, X } from "lucide-react";

type Preferences = {
  textScale: number;
  highContrast: boolean;
  highlightLinks: boolean;
  reduceMotion: boolean;
  textSpacing: boolean;
  nightMode: boolean;
};
const defaults: Preferences = {
  textScale: 100,
  highContrast: false,
  highlightLinks: false,
  reduceMotion: false,
  textSpacing: false,
  nightMode: false,
};
const storageKey = "guia-social-accessibility";

export default function AccessibilityTools() {
  const [preferences, setPreferences] = useState<Preferences>(defaults);
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null");
      if (saved && typeof saved === "object") {
        setPreferences({
          textScale:
            typeof saved.textScale === "number" &&
            Number.isFinite(saved.textScale)
              ? Math.min(
                  150,
                  Math.max(100, Math.round(saved.textScale / 10) * 10),
                )
              : 100,
          highContrast: saved.highContrast === true,
          highlightLinks: saved.highlightLinks === true,
          reduceMotion: saved.reduceMotion === true,
          textSpacing: saved.textSpacing === true,
          nightMode: saved.nightMode === true,
        });
      }
    } catch {
      /* Preferences remain usable when browser storage is unavailable. */
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    const root = document.documentElement;
    root.style.setProperty("--text-scale", String(preferences.textScale / 100));
    root.dataset.highContrast = String(preferences.highContrast);
    root.dataset.highlightLinks = String(preferences.highlightLinks);
    root.dataset.reduceMotion = String(preferences.reduceMotion);
    root.dataset.textSpacing = String(preferences.textSpacing);
    root.dataset.nightMode = String(preferences.nightMode);
    try {
      localStorage.setItem(storageKey, JSON.stringify(preferences));
    } catch {
      /* Memory-only fallback. */
    }
  }, [preferences, ready]);

  function toggle(
    key:
      | "highContrast"
      | "highlightLinks"
      | "reduceMotion"
      | "textSpacing"
      | "nightMode",
  ) {
    setPreferences((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <>
      <button
        type="button"
        className="night-mode-toggle"
        aria-pressed={preferences.nightMode}
        aria-label={
          preferences.nightMode
            ? "Desativar modo noturno"
            : "Ativar modo noturno"
        }
        title={
          preferences.nightMode
            ? "Desativar modo noturno"
            : "Ativar modo noturno"
        }
        onClick={() => toggle("nightMode")}
      >
        {preferences.nightMode ? (
          <Sun size={21} aria-hidden="true" />
        ) : (
          <Moon size={21} aria-hidden="true" />
        )}
        <span>Modo noturno</span>
      </button>
      <button
        ref={triggerRef}
        className="accessibility-trigger"
        aria-label="Abrir ferramentas de acessibilidade"
        title="Acessibilidade"
        aria-haspopup="dialog"
        aria-controls="accessibility-panel"
        aria-expanded={open}
        onClick={() => {
          dialogRef.current?.showModal();
          setOpen(true);
        }}
      >
        <svg
          width="30"
          height="30"
          viewBox="0 0 32 32"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="16"
            cy="16"
            r="14"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <circle cx="16" cy="8" r="3" fill="currentColor" />
          <path
            d="M6 13Q16 19 26 13M16 16V20M16 20L10 27M16 20L22 27"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="6" cy="13" r="2" fill="currentColor" />
          <circle cx="26" cy="13" r="2" fill="currentColor" />
          <circle cx="10" cy="27" r="2" fill="currentColor" />
          <circle cx="22" cy="27" r="2" fill="currentColor" />
        </svg>
      </button>
      <dialog
        ref={dialogRef}
        id="accessibility-panel"
        className="accessibility-panel"
        aria-labelledby="accessibility-title"
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          const controls = Array.from(
            event.currentTarget.querySelectorAll<HTMLElement>(
              'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
            ),
          ).filter((element) => element.getClientRects().length > 0);
          const first = controls[0];
          const last = controls[controls.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }}
        onClose={() => {
          setOpen(false);
          triggerRef.current?.focus();
        }}
      >
        <div className="accessibility-heading">
          <h2 id="accessibility-title">Acessibilidade</h2>
          <button
            autoFocus
            type="button"
            aria-label="Fechar acessibilidade"
            onClick={() => dialogRef.current?.close()}
          >
            <X size={22} aria-hidden="true" />
          </button>
        </div>
        <div className="text-size-control">
          <span id="text-size-label">Tamanho do texto</span>
          <div role="group" aria-labelledby="text-size-label">
            <button
              type="button"
              aria-label="Diminuir texto"
              disabled={preferences.textScale <= 100}
              onClick={() =>
                setPreferences((p) => ({ ...p, textScale: p.textScale - 10 }))
              }
            >
              <Minus size={20} aria-hidden="true" />
            </button>
            <output aria-live="polite" aria-label="Tamanho atual do texto">
              {preferences.textScale}%
            </output>
            <button
              type="button"
              aria-label="Aumentar texto"
              disabled={preferences.textScale >= 150}
              onClick={() =>
                setPreferences((p) => ({ ...p, textScale: p.textScale + 10 }))
              }
            >
              <Plus size={20} aria-hidden="true" />
            </button>
          </div>
        </div>
        {(
          [
            ["highContrast", "Alto contraste"],
            ["highlightLinks", "Destacar links"],
            ["textSpacing", "Aumentar espaçamento"],
            ["reduceMotion", "Reduzir movimento"],
          ] as const
        ).map(([key, label]) => (
          <button
            type="button"
            key={key}
            className="accessibility-toggle"
            role="switch"
            aria-checked={preferences[key]}
            onClick={() => toggle(key)}
          >
            <span>{label}</span>
            <span className="switch-track" aria-hidden="true">
              <span />
            </span>
          </button>
        ))}
        <details className="keyboard-help">
          <summary>Navegação por teclado</summary>
          <ul>
            <li>
              <kbd>Tab</kbd> avança; <kbd>Shift + Tab</kbd> volta.
            </li>
            <li>
              <kbd>Enter</kbd> ou <kbd>Espaço</kbd> ativa botões.
            </li>
            <li>
              <kbd>Esc</kbd> fecha este painel.
            </li>
            <li>
              No chat: <kbd>Enter</kbd> envia; <kbd>Shift + Enter</kbd> cria uma
              linha.
            </li>
          </ul>
        </details>
        <button
          type="button"
          className="accessibility-reset"
          onClick={() => setPreferences({ ...defaults })}
        >
          <RotateCcw size={18} aria-hidden="true" />
          Restaurar padrão
        </button>
      </dialog>
    </>
  );
}
