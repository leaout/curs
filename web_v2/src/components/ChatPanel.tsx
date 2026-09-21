import { useEffect, useRef, useState } from "react";

import type { ChatMessage, StrategyPromptVersion } from "../types";

interface ChatPanelProps {
  messages: ChatMessage[];
  versions: StrategyPromptVersion[];
  busy: boolean;
  onSend: (content: string) => void;
}

export function ChatPanel({ messages, versions, busy, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const [showVersions, setShowVersions] = useState(false);
  const messageEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messageEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const submit = () => {
    const content = draft.trim();
    if (!content || busy) return;
    setDraft("");
    onSend(content);
  };

  return (
    <aside className="chat-panel panel-edge">
      <div className="chat-heading">
        <div>
          <p className="eyebrow">STRATEGY COPILOT</p>
          <h2>策略对话</h2>
        </div>
        <button className={`version-button ${showVersions ? "active" : ""}`} onClick={() => setShowVersions((value) => !value)}>
          <span>⌘</span> Prompt v{versions.find((version) => version.active)?.version ?? 1}
        </button>
      </div>

      {showVersions && (
        <div className="versions-popover">
          <div className="versions-title"><span>Prompt 版本</span><small>自动保存</small></div>
          {versions.map((version) => (
            <div className={`version-row ${version.active ? "active" : ""}`} key={version.version}>
              <span className="version-number">v{version.version}</span>
              <span>{version.summary}<small>{version.createdAt}</small></span>
              {version.active && <b>当前</b>}
            </div>
          ))}
        </div>
      )}

      <div className="chat-messages">
        <div className="chat-date"><span>今天</span></div>
        {messages.map((message) => (
          <article key={message.id} className={`message ${message.role}`}>
            <div className="message-avatar">{message.role === "assistant" ? "V" : "你"}</div>
            <div className="message-content">
              <div className="message-topline">
                <strong>{message.role === "assistant" ? "Vibe Agent" : "你"}</strong>
                <span>{message.timestamp}</span>
                {message.version && <em>v{message.version}</em>}
              </div>
              <p>{message.content}</p>
            </div>
          </article>
        ))}
        {busy && (
          <article className="message assistant">
            <div className="message-avatar">V</div>
            <div className="message-content typing"><i /><i /><i /></div>
          </article>
        )}
        <div ref={messageEnd} />
      </div>

      <div className="chat-suggestions">
        {["降低仓位", "解释最新决策", "暂停交易"].map((text) => (
          <button key={text} onClick={() => setDraft(text)}>{text}</button>
        ))}
      </div>
      <div className="composer">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="直接告诉 Agent 你想怎么调整策略…"
          rows={3}
        />
        <div className="composer-footer">
          <span>↵ 发送 · Shift ↵ 换行</span>
          <button onClick={submit} disabled={!draft.trim() || busy} aria-label="发送消息">↑</button>
        </div>
      </div>
      <p className="chat-warning">策略修改将生成新版本，并从下一根闭合 K 线开始生效</p>
    </aside>
  );
}
