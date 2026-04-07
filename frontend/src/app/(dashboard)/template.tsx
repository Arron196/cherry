"use client";

import { motion } from "framer-motion";

export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
    return (
        <motion.div
            initial={{ opacity: 0, filter: "blur(4px)", y: 8 }}
            animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
            transition={{
                duration: 0.4,
                ease: [0.22, 1, 0.36, 1], // easeOutQuint-like curve
            }}
            className="flex-1 w-full h-full flex flex-col min-w-0" // Important for flex layout to continue working
        >
            {children}
        </motion.div>
    );
}