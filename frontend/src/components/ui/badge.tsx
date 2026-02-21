import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Shadcn-style Badge with clinical colour variants                  */
/* ------------------------------------------------------------------ */

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold leading-5 transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-white/10 bg-white/5 text-fg",
        secondary:
          "border-white/[0.06] bg-white/[0.03] text-fg-dim",
        destructive:
          "border-danger/30 bg-danger/15 text-danger",
        outline:
          "border-white/10 text-fg",
        success:
          "border-safe/30 bg-safe/15 text-safe",
        warning:
          "border-caution/30 bg-caution/15 text-caution",
        info:
          "border-info/30 bg-info/15 text-info",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
