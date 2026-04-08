import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
    "edge-highlight inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide transition-[background-color,border-color,color,box-shadow] focus:outline-none focus:ring-2 focus:ring-primary-300/70",
    {
        variants: {
            variant: {
                default:
                    "border-primary-300/35 bg-primary-500/24 text-primary-100 hover:bg-primary-500/35",
                secondary:
                    "border-slate-600/75 bg-slate-800/82 text-slate-100 hover:border-slate-500/80 hover:bg-slate-700/86",
                destructive:
                    "border-rose-300/40 bg-rose-600/30 text-rose-100 hover:bg-rose-600/45",
                outline: "border-slate-500/90 bg-slate-900/55 text-slate-100",
                success: "border-emerald-300/45 bg-emerald-600/30 text-emerald-100 hover:bg-emerald-600/44",
                warning: "border-amber-300/50 bg-amber-500/36 text-amber-50 hover:bg-amber-500/46",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
);

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, ...props }: BadgeProps) {
    return (
        <div className={cn(badgeVariants({ variant }), className)} {...props} />
    );
}

export { Badge, badgeVariants };
