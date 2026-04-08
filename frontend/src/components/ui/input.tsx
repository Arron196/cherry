import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
    ({ className, type, ...props }, ref) => {
        return (
            <input
                type={type}
                className={cn(
                    "edge-highlight flex h-11 w-full rounded-xl border border-slate-600/80 bg-slate-900/74 px-3 py-2 text-sm text-slate-100 shadow-[0_12px_22px_-18px_rgba(2,6,23,0.9)] transition-[background-color,border-color,box-shadow,transform] placeholder:text-slate-300/80 file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:border-cyan-300/80 focus-visible:bg-slate-900/92 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/35 focus-visible:shadow-[0_0_0_1px_rgba(34,211,238,0.35),0_18px_34px_-22px_rgba(34,211,238,0.55)] disabled:cursor-not-allowed disabled:opacity-50",
                    className
                )}
                ref={ref}
                {...props}
            />
        );
    }
);
Input.displayName = "Input";

export { Input };
