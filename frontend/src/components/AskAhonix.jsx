import React, { useEffect, useRef, useState } from "react";
import { X, Sparkles, ArrowUp, Loader2, AlertTriangle } from "lucide-react";
import { useUI } from "@/context/UIContext";
import { API } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { Logo } from "@/components/Logo";

const MAX_QUESTION_LENGTH = 5000;

const QUICK_PROMPTS = [
  "What should I focus on today?",
  "Why is my profit different from revenue?",
  "Which product should I restock first?",
  "Which campaign is actually making money?",
  "Where am I losing money?",
  "What market should I expand into next?",
];

export function AskAhonix() {
  const { askOpen, setAskOpen, askSeed, setAskSeed } = useUI();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const sessionRef = useRef(null);
  const scrollRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (askOpen && askSeed) {
      const q = typeof askSeed === "string" ? askSeed : askSeed.title;
      setInput(q);
      setAskSeed(null);
    }
  }, [askOpen, askSeed, setAskSeed]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (question) => {
    const q = (question ?? input).trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: sessionRef.current }),
      });
      if (res.status === 429) {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: "⚠️ You're sending questions too quickly. Please wait a moment and try again.",
          };
          return copy;
        });
        return;
      }
      if (res.status === 422) {
        const err = await res.json().catch(() => null);
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: `⚠️ ${err?.detail || "Invalid question. Please check your input."}`,
          };
          return copy;
        });
        return;
      }
      if (!res.ok || !res.body) throw new Error("stream failed");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.delta) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                role: "assistant",
                content: copy[copy.length - 1].content + payload.delta,
              };
              return copy;
            });
          } else if (payload.session_id) {
            sessionRef.current = payload.session_id;
          } else if (payload.error) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { role: "assistant", content: "⚠️ " + payload.error };
              return copy;
            });
          }
        }
      }
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: "⚠️ I couldn't reach the analyst right now. Please try again.",
        };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  if (!askOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="ask-ahonix-drawer">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setAskOpen(false)} />
      <div className="relative flex h-full w-full max-w-xl flex-col border-l border-[#1E2235] bg-[#0B0D14] shadow-2xl animate-fade-up">
        <div className="flex items-center justify-between border-b border-[#1E2235] px-5 py-4">
          <div className="flex items-center gap-2">
            <Logo size={22} showText={false} />
            <div>
              <p className="font-display text-sm font-bold text-[#F8FAFC]">
                Ask AHONIX <span className="text-emerald-400">✦</span>
              </p>
              <p className="text-xs text-[#64748B]">Your commerce analyst · reasons over your data</p>
            </div>
          </div>
          <button
            onClick={() => setAskOpen(false)}
            className="rounded-lg p-2 text-[#94A3B8] hover:bg-[#161926]"
            data-testid="ask-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {messages.length === 0 && (
            <div>
              <div className="mb-4 flex items-start gap-3 rounded-xl border border-[#1E2235] bg-[#121420] p-4">
                <Sparkles size={16} className="mt-0.5 text-emerald-400" />
                <p className="text-sm text-[#CBD5E1]">
                  Ask me anything about your business. I analyze your sales, profit, inventory, marketing and
                  returns — and tell you what to do next.
                </p>
              </div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[#64748B]">Try asking</p>
              <div className="space-y-2">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    className="w-full rounded-lg border border-[#1E2235] bg-[#0F111A] px-3 py-2.5 text-left text-sm text-[#CBD5E1] transition-colors hover:border-emerald-500/40 hover:bg-[#121420]"
                    data-testid="ask-quick-prompt"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-emerald-500/15 px-4 py-2.5 text-sm text-emerald-100">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="rounded-xl border border-[#1E2235] bg-[#121420] p-4" data-testid="ask-answer">
                {m.content ? (
                  <div className="markdown" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                ) : (
                  <div className="flex items-center gap-2 text-sm text-[#64748B]">
                    <Loader2 size={14} className="animate-spin" /> Analyzing your data…
                  </div>
                )}
              </div>
            )
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-[#1E2235] p-4">
          <div className="flex items-end gap-2 rounded-xl border border-[#2D334B] bg-[#161926] p-2 focus-within:border-emerald-500/50">
            <textarea
              value={input}
              onChange={(e) => {
                if (e.target.value.length <= MAX_QUESTION_LENGTH) {
                  setInput(e.target.value);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder="Ask about profit, returns, restock, campaigns…"
              className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-[#F8FAFC] outline-none placeholder:text-[#475569]"
              data-testid="ask-ahonix-input"
              maxLength={MAX_QUESTION_LENGTH}
            />
            <button
              onClick={() => send()}
              disabled={streaming || !input.trim() || input.length > MAX_QUESTION_LENGTH}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-emerald-950 disabled:opacity-40"
              data-testid="ask-ahonix-submit"
            >
              {streaming ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
            </button>
          </div>
          {input.length > MAX_QUESTION_LENGTH * 0.9 && (
            <div className="mt-1 flex items-center gap-1 text-[10px] text-amber-400">
              <AlertTriangle size={10} />
              {input.length}/{MAX_QUESTION_LENGTH} characters
            </div>
          )}
          <p className="mt-2 text-center text-[10px] text-[#475569]">
            AHONIX reasons over demo data. Figures are estimates, not financial advice.
          </p>
        </div>
      </div>
    </div>
  );
}
