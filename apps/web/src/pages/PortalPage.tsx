import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge, Button, Panel } from "../components/ui";
import { useAppStore } from "../store";
import type { ChatMessage } from "../types";

export function PortalPage() {
  const { refreshAll, setToast } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void api.chat.messages().then(setMessages).catch(() => undefined);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    if (!input.trim() || sending) return;
    setSending(true);
    const text = input.trim();
    setInput("");
    try {
      const res = await api.chat.send(text);
      setMessages(res.messages);
      setToast("Demanda registrada e triada");
      await refreshAll();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "Falha no portal");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[1.2fr_0.8fr]">
      <Panel
        title="Portal Manus"
        action={<Badge tone="accent">supervisor</Badge>}
        className="min-h-[70vh]"
      >
        <div className="flex h-[58vh] flex-col">
          <div className="flex-1 space-y-3 overflow-y-auto pr-1">
            {!messages.length ? (
              <div className="rounded-[24px] border border-dashed border-[var(--line)] px-5 py-8">
                <h3 className="text-xl font-semibold">Descreva o que precisa</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Ex.: “Criar uma API para cadastrar clientes, autenticar usuários e consultar
                  pedidos.”
                </p>
              </div>
            ) : null}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`max-w-[90%] rounded-[22px] px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "ml-auto bg-[var(--accent)] text-white"
                    : "bg-white border border-[var(--line)]"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                {msg.card_id ? (
                  <Link
                    to={`/cards/${msg.card_id}`}
                    className="mt-2 inline-block text-xs font-semibold underline"
                  >
                    Abrir cartão
                  </Link>
                ) : null}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <div className="mt-4 flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={3}
              placeholder="Escreva a demanda..."
              className="flex-1 resize-none rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none focus:ring-2 focus:ring-[var(--accent)]"
            />
            <Button onClick={() => void send()} disabled={sending} className="self-end">
              {sending ? "..." : "Enviar"}
            </Button>
          </div>
        </div>
      </Panel>

      <div className="space-y-4">
        <Panel title="O que o portal faz">
          <ul className="space-y-3 text-sm leading-relaxed text-[var(--muted)]">
            <li>Cria cartão a partir de linguagem natural</li>
            <li>Dispara triagem, requisitos e plano via LangGraph + LLM</li>
            <li>Pausa em aprovação humana antes do enxame</li>
            <li>Explica o estado atual e aponta o próximo passo</li>
          </ul>
        </Panel>
        <Panel title="Sugestões">
          <div className="space-y-2">
            {[
              "Criar um sistema de cadastro e acompanhamento de contratos.",
              "Corrigir autenticação JWT que expira cedo demais.",
              "Documentar a API de pedidos com exemplos OpenAPI.",
            ].map((sample) => (
              <button
                key={sample}
                onClick={() => setInput(sample)}
                className="w-full rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3 text-left text-sm hover:border-[var(--accent)]"
              >
                {sample}
              </button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
