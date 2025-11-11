"use client";

import { welcomePrompts, promptColors, type SuggestedPrompt } from "@/lib/promptLibrary";
import { cn } from "@/utils/cn";

interface SuggestedPromptsProps {
  onPromptClick: (text: string) => void;
}

export function SuggestedPrompts({ onPromptClick }: SuggestedPromptsProps) {
  return (
    <div className="w-full max-w-4xl mx-auto px-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {welcomePrompts.map((prompt) => (
          <PromptCard
            key={prompt.id}
            prompt={prompt}
            onClick={() => onPromptClick(prompt.text)}
          />
        ))}
      </div>
    </div>
  );
}

interface PromptCardProps {
  prompt: SuggestedPrompt;
  onClick: () => void;
}

function PromptCard({ prompt, onClick }: PromptCardProps) {
  const colorClasses = promptColors[prompt.color as keyof typeof promptColors] || promptColors.blue;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex flex-col items-start text-left p-4 rounded-lg border-2 transition-all duration-200",
        "hover:shadow-md hover:scale-105 active:scale-100",
        colorClasses
      )}
    >
      {/* Icon */}
      <div className="text-2xl mb-2">{prompt.icon}</div>

      {/* Category label */}
      <div className="text-xs font-medium opacity-70 mb-1">
        {prompt.category}
      </div>

      {/* Main prompt text */}
      <div className="text-sm font-semibold leading-tight mb-2">
        {prompt.text}
      </div>

      {/* Description */}
      <div className="text-xs opacity-60">
        {prompt.description}
      </div>

      {/* Hover arrow indicator */}
      <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 7l5 5m0 0l-5 5m5-5H6"
          />
        </svg>
      </div>
    </button>
  );
}
