import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

// Rendered Markdown preview. Styling lives in the `.md-preview` rules in index.css
// (Tailwind v4 ships without the typography plugin, so we hand-roll a compact prose).
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("md-preview", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}
