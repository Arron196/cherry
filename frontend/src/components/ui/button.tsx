import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const buttonVariants = cva(
    "inline-flex cursor-pointer items-center justify-center rounded-xl text-sm font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300/75 focus-visible:ring-offset-0 disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
    {
        variants: {
            variant: {
                default:
                    "bg-gradient-to-r from-primary-300 via-primary-400 to-accent-teal text-slate-950 shadow-[0_14px_28px_-16px_rgba(34,211,238,0.78)] hover:brightness-110 hover:shadow-[0_20px_38px_-22px_rgba(34,211,238,0.9)] hover:-translate-y-0.5",
                destructive:
                    "bg-rose-700 text-rose-50 shadow-sm hover:bg-rose-600 hover:shadow-[0_10px_20px_-10px_rgba(225,29,72,0.6)] hover:-translate-y-0.5",     
                outline:
                    "border border-slate-600/80 bg-slate-900/70 text-slate-100 shadow-sm hover:border-cyan-400/55 hover:bg-slate-800/82 hover:text-cyan-100 hover:shadow-[0_10px_20px_-10px_rgba(34,211,238,0.4)] hover:-translate-y-0.5",   
                secondary:
                    "border border-slate-700/70 bg-slate-800/82 text-slate-100 shadow-sm hover:border-emerald-400/45 hover:bg-slate-700/88 hover:shadow-[0_10px_20px_-10px_rgba(16,185,129,0.3)] hover:-translate-y-0.5",
                ghost: "text-slate-200 hover:bg-slate-800/80 hover:text-white hover:-translate-y-0.5", 
                link: "text-primary-300 underline-offset-4 hover:text-primary-200 hover:underline hover:-translate-y-0.5",
            },
            size: {
                default: "h-10 px-4 py-2",
                sm: "h-8 px-3 text-xs",
                lg: "h-11 px-8",
                icon: "h-9 w-9",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
);

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    asChild?: boolean;
    loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    ({ className, variant, size, asChild = false, loading = false, children, disabled, ...props }, ref) => {
        return (
            <button
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                disabled={loading || disabled}
                {...props}
            >
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {children}
            </button>
        );
    }
);
Button.displayName = "Button";

export { Button, buttonVariants };
