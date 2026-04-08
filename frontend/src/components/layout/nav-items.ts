import {
    LayoutDashboard,
    Package,
    Activity,
    AlertTriangle,
    ShieldCheck,
    Server,
    Wrench,
    type LucideIcon,
} from "lucide-react";

export interface NavItem {
    title: string;
    href: string;
    icon: LucideIcon;
    section: "business" | "technical"; // Explicitly separating business and tech views
}

export const navItems: NavItem[] = [
    // ----------------------------------------------------
    // 面向业务监管员（合规 / 品控 / 仓储经理）的视图
    // ----------------------------------------------------
    {
        title: "全案总览",
        href: "/",
        icon: LayoutDashboard,
        section: "business",
    },
    {
        title: "追溯批次",
        href: "/batches",
        icon: Package,
        section: "business",
    },
    {
        title: "实时事件表",
        href: "/events",
        icon: Activity,
        section: "business",
    },
    {
        title: "品质告警台",
        href: "/alerts",
        icon: AlertTriangle,
        section: "business",
    },
    
    // ----------------------------------------------------
    // 面向系统工程师（实施 / 运维开发 / 数据后台）的视图
    // ----------------------------------------------------
    {
        title: "链上锚定任务",
        href: "/admin/anchoring",
        icon: ShieldCheck,
        section: "technical",
    },
    {
        title: "物联设备管理",
        href: "/admin/devices",
        icon: Server,
        section: "technical",
    },
    {
        title: "API 测试沙盒",
        href: "/api-tools",
        icon: Wrench,
        section: "technical",
    },
];
